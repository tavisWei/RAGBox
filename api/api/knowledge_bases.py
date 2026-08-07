"""Knowledge base routes with real storage integration."""

import asyncio
import os
import uuid

import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional

from api.services.agent_index_service import (
    agent_index_service,
    resolve_default_llm_config,
)
from api.services.document_processor import DocumentProcessor, DocumentChunk
from api.services.knowledge_base_store import knowledge_base_store
from api.services.model_provider_service import model_provider_service
from api.services.rag_service import RAGService, parse_pgvector_dsn
from api.services.resource_config_service import ResourceLevel
from api.core.rag.splitter.splitter_factory import SplitterFactory
from .deps import get_current_user

router = APIRouter()


RAG_PLAN_PRESETS = {
    "low": {
        "key": "low",
        "name": "轻量起步方案",
        "summary": "单机本地 RAG，使用 SQLite FTS 全文/关键词检索 + 可选本地向量替代，适合个人、小团队和低成本私有部署。",
        "cost_level": "低",
        "quality_level": "轻量可用",
        "architecture": "SQLite 本地存储 + FTS5 全文/关键词检索；可在本地 embedding 可用时启用 SQLite BLOB 暴力向量检索",
        "recommended_backend": "sqlite",
        "vector_backend": "sqlite-builtin",
        "datastore_note": "最低成本不依赖外部向量库；语义检索可用 SQLite 本地向量替代方案，但规模大时应升级到团队标准。",
        "best_for": ["个人/小团队", "小文档集", "低频查询", "最小运维"],
        "tradeoffs": ["向量检索为本地暴力相似度", "不适合百万级分块", "不启用重排"],
        "hardware_tier": "low",
        "embedding_provider": "ollama",
        "embedding_model": "nomic-embed-text",
        "splitter_config": {
            "type": "recursive",
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
        "retrieval_config": {
            "methods": ["fulltext", "keyword"],
            "top_k": 5,
            "fusion_mode": "simple",
            "query_expansion": "none",
            "rerank_mode": "none",
        },
    },
    "medium": {
        "key": "medium",
        "name": "团队标准方案",
        "summary": "生产推荐 RAG，使用 PostgreSQL + pgvector 承载业务数据、全文检索与向量检索。",
        "cost_level": "中",
        "quality_level": "生产推荐",
        "architecture": "PostgreSQL + pgvector + tsvector 全文检索 + RRF 混合召回 + Cross-Encoder 重排",
        "recommended_backend": "pgvector",
        "vector_backend": "pgvector",
        "datastore_note": "适合团队生产使用；如果当前运行后端仍是 SQLite，需配置 DATA_STORE_TYPE=pgvector 并安装 pgvector 扩展。",
        "best_for": ["团队知识库", "常规生产问答", "效果/成本平衡"],
        "tradeoffs": [
            "需要 PostgreSQL 与 pgvector 扩展",
            "需要真实 embedding 配置",
            "重排会增加延迟",
        ],
        "hardware_tier": "medium",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "splitter_config": {
            "type": "recursive",
            "chunk_size": 500,
            "chunk_overlap": 100,
        },
        "retrieval_config": {
            "methods": ["hybrid"],
            "top_k": 10,
            "fusion_mode": "rrf",
            "query_expansion": "multi_query",
            "rerank_mode": "cross_encoder",
        },
    },
    "high": {
        "key": "high",
        "name": "企业增强方案",
        "summary": "企业级 RAG，面向大规模、多租户、复杂过滤与高质量问答，使用搜索/向量集群能力。",
        "cost_level": "高",
        "quality_level": "效果优先",
        "architecture": "Elasticsearch dense_vector/全文检索集群 + HyDE 查询扩展 + LLM 列表式重排；可迁移到 Qdrant/Milvus 等专用向量库",
        "recommended_backend": "elasticsearch",
        "vector_backend": "elasticsearch-dense-vector",
        "datastore_note": "适合企业级集群部署；如需要专用向量库，Qdrant 适合多数生产场景，Milvus 适合超大规模。",
        "best_for": ["大规模文档", "复杂问题", "多租户/企业检索", "质量优先"],
        "tradeoffs": ["组件更重", "需要集群运维", "HyDE 与 LLM 重排成本更高"],
        "hardware_tier": "high",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-large",
        "splitter_config": {
            "type": "parent_child",
            "chunk_size": 1000,
            "chunk_overlap": 200,
        },
        "retrieval_config": {
            "methods": ["hybrid", "semantic", "fulltext"],
            "top_k": 20,
            "fusion_mode": "weighted",
            "query_expansion": "hyde",
            "rerank_mode": "llm_listwise",
        },
    },
    "agent": {
        "key": "agent",
        "name": "Agent 主动检索方案",
        "summary": "主动 Agent RAG：素材导入后由 LLM 生成索引摘要；对话时 Agent 自主识别意图、决定何时检索并多轮取料，再加工回答。",
        "cost_level": "中",
        "quality_level": "智能路由",
        "architecture": "导入期 LLM 生成索引摘要（标题/关键词/典型问题）并指向原文档；对话期 Function-Calling Agent 通过 kb_search 工具按需检索，两段式取料（索引摘要层 → 文档块级）",
        "recommended_backend": "sqlite",
        "vector_backend": "sqlite-builtin",
        "datastore_note": "默认沿用 SQLite 本地存储，可在存储配置中切换 pgvector/ES；索引摘要与块向量共存于同一后端。",
        "best_for": ["自创建 Agent 对话", "素材库问答", "需要意图识别与引用溯源的场景"],
        "tradeoffs": ["导入期每文档多一次 LLM 摘要调用", "对话期 Agent 循环增加首 token 延迟", "依赖模型 function-calling 能力，失败时自动降级标准检索"],
        "hardware_tier": "medium",
        "rag_mode": "agent",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "splitter_config": {
            "type": "recursive",
            "chunk_size": 500,
            "chunk_overlap": 100,
        },
        "retrieval_config": {
            "methods": ["hybrid"],
            "top_k": 10,
            "fusion_mode": "rrf",
            "query_expansion": "none",
            "rerank_mode": "none",
        },
    },
}

# In-memory knowledge base storage (replace with database in production)
_store_data = knowledge_base_store.read_all()
_knowledge_bases: dict = _store_data.get("knowledge_bases", {})
_knowledge_base_documents: dict = _store_data.get("documents", {})


def _persist_kb_state() -> None:
    knowledge_base_store.write_all(
        {
            "knowledge_bases": _knowledge_bases,
            "documents": _knowledge_base_documents,
        }
    )


def _kb_resource_level(kb_id: str) -> ResourceLevel:
    tier = (_knowledge_bases.get(kb_id, {}).get("hardware_tier") or "medium").lower()
    if tier == "low":
        return ResourceLevel.LOW
    if tier == "high":
        return ResourceLevel.HIGH
    return ResourceLevel.MEDIUM


def resolve_datastore_config(kb: dict) -> dict:
    """Single source of truth for a KB's data-store selection.

    Precedence: KB-level datastore config > DATA_STORE_TYPE env > enabled
    datastore component (components page, non-SQLite preferred) > the RAG
    plan's recommended_backend > sqlite.
    """
    datastore = kb.get("datastore") or {}
    store_type = datastore.get("type")
    if store_type:
        config: dict = {"data_store_type": store_type}
        if store_type == "pgvector":
            if datastore.get("dsn"):
                config["datastore"] = parse_pgvector_dsn(datastore["dsn"])
            else:
                # Individual fields only; anything unset falls through to
                # PGVECTOR_* env defaults inside RAGService.
                fields = {
                    key: datastore[key]
                    for key in ("host", "port", "user", "password", "database")
                    if datastore.get(key) not in (None, "")
                }
                if "port" in fields:
                    fields["port"] = int(fields["port"])
                if fields:
                    config["datastore"] = fields
        return config

    env_type = os.getenv("DATA_STORE_TYPE")
    if env_type:
        return {"data_store_type": env_type}

    from api.services.component_config_service import component_config_service

    active = component_config_service.get_active_datastore()
    if active:
        return active

    if not kb:
        # No knowledge base context (e.g. plain chat): never default to an
        # external backend the deployment may not have.
        return {"data_store_type": "sqlite"}

    plan = _get_rag_plan(kb.get("rag_plan"))
    runtime_store = plan.get("recommended_backend") or "sqlite"
    return {"data_store_type": runtime_store}


def _mask_dsn(dsn: str) -> str:
    """Mask the password inside a DSN for API output."""
    try:
        parsed = urlparse(dsn)
        if parsed.password is None:
            return dsn
        credentials = parsed.username or ""
        masked_netloc = f"{credentials}:****@{parsed.hostname or ''}"
        if parsed.port:
            masked_netloc += f":{parsed.port}"
        return urlunparse(
            (parsed.scheme, masked_netloc, parsed.path, "", "", "")
        )
    except Exception:
        return "****"


def _masked_datastore(kb: dict) -> Optional[dict]:
    datastore = kb.get("datastore")
    if not datastore:
        return None
    masked = dict(datastore)
    if masked.get("dsn"):
        masked["dsn"] = _mask_dsn(masked["dsn"])
    if masked.get("password"):
        masked["password"] = "****"
    return masked


def _kb_datastore_config(kb_id: str) -> dict:
    kb = _knowledge_bases.get(kb_id, {})
    plan = _get_rag_plan(kb.get("rag_plan"))
    config = resolve_datastore_config(kb)
    config.update(
        {
            "vector_enabled": plan.get("hardware_tier") != "low"
            or plan.get("vector_backend") == "sqlite-builtin",
            "embedding_provider": kb.get("embedding_provider")
            or plan.get("embedding_provider"),
            "embedding_model": kb.get("embedding_model") or plan.get("embedding_model"),
        }
    )
    return config


def _schedule_agent_index(
    background_tasks: BackgroundTasks,
    kb_id: str,
    document_id: str,
    doc_name: str,
    text: str,
) -> None:
    """Queue agent-index generation after a document is ingested.

    No-op for non-agent KBs. Without a configured default model the entry is
    recorded as an error so the UI can surface it instead of silently skipping.
    """
    kb = _knowledge_bases.get(kb_id, {})
    if kb.get("rag_mode") != "agent":
        return
    llm_config = resolve_default_llm_config()
    if llm_config is None:
        agent_index_service.upsert_entry(
            kb_id,
            document_id,
            name=doc_name,
            status="error",
            error="未配置默认模型供应商，无法生成 Agent 索引",
        )
        return
    agent_index_service.upsert_entry(
        kb_id, document_id, name=doc_name, status="pending"
    )
    background_tasks.add_task(
        agent_index_service.schedule_index,
        kb_id,
        document_id,
        doc_name,
        text,
        {**_kb_datastore_config(kb_id), **llm_config},
        _kb_resource_level(kb_id),
    )


def _qa_llm_function():
    """Sync (prompt -> str) bridge for QA-pair generation at ingestion time.

    Opt-in via QA_GENERATION_PROVIDER / QA_GENERATION_MODEL env vars; returns
    None when unconfigured, in which case QA indexing stays regex-only.
    """
    provider = os.getenv("QA_GENERATION_PROVIDER")
    model = os.getenv("QA_GENERATION_MODEL")
    if not provider or not model:
        return None
    from api.services.llm_service import ChatConfig, ChatMessage, LLMService
    from api.services.model_provider_service import model_provider_service

    active = model_provider_service.get_active_provider_config(provider)
    credentials = (active or {}).get("credentials", {})
    service = LLMService(
        provider=provider,
        model=model,
        api_key=credentials.get("api_key"),
        base_url=credentials.get("base_url"),
    )

    def llm_fn(prompt: str) -> str:
        # Runs inside an asyncio.to_thread worker: no running loop there.
        response = asyncio.run(
            service.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                config=ChatConfig(max_tokens=2048, temperature=0.3),
            )
        )
        return response.content

    return llm_fn


def _chunks_via_index_processor(
    index_mode: str,
    text: str,
    metadata: dict,
    splitter_config: dict,
) -> List[DocumentChunk]:
    """Transform text into chunks with a non-paragraph index processor."""
    from api.core.rag.index_processor.processor.parent_child_index_processor import (
        ParentChildIndexProcessor,
        flatten_parent_child,
    )
    from api.core.rag.index_processor.processor.qa_index_processor import (
        QAIndexProcessor,
    )
    from api.core.rag.models.document import Document as ModelDocument

    base = ModelDocument(page_content=text, metadata=metadata or {})
    if index_mode == "parent_child":
        processor = ParentChildIndexProcessor(
            parent_chunk_size=int(splitter_config.get("parent_chunk_size", 2048)),
            child_chunk_size=int(splitter_config.get("chunk_size", 256)),
            chunk_overlap=int(splitter_config.get("chunk_overlap", 64)),
        )
        transformed = flatten_parent_child(processor.transform([base]))
    elif index_mode == "qa":
        processor = QAIndexProcessor(
            llm_generate=bool(splitter_config.get("qa_llm_generate")),
            llm_function=_qa_llm_function(),
        )
        transformed = processor.transform([base])
    else:
        raise HTTPException(400, f"Unsupported index_mode: {index_mode}")
    return [
        DocumentChunk(
            content=doc.page_content,
            chunk_index=i,
            start_char=0,
            end_char=len(doc.page_content),
            metadata=doc.metadata or {},
        )
        for i, doc in enumerate(transformed)
    ]


def _map_split_chunks_to_metadata(
    split_chunks: List[str], source_chunks: List[DocumentChunk], joined_text: str
) -> List[DocumentChunk]:
    processed_chunks: List[DocumentChunk] = []
    start_char = 0
    for index, chunk in enumerate(split_chunks):
        chunk_start = joined_text.find(chunk, start_char)
        if chunk_start < 0:
            chunk_start = start_char
        chunk_end = chunk_start + len(chunk)
        matched = [
            item
            for item in source_chunks
            if item.start_char < chunk_end and item.end_char > chunk_start
        ]
        chunk_metadata = {}
        for item in matched:
            chunk_metadata.update(item.metadata)
        pages = sorted(
            {page for item in matched for page in item.metadata.get("pages", [])}
        )
        paragraphs = sorted(
            {
                paragraph
                for item in matched
                for paragraph in item.metadata.get("paragraphs", [])
            }
        )
        block_types = sorted(
            {
                block_type
                for item in matched
                for block_type in item.metadata.get("block_types", [])
            }
        )
        if pages:
            chunk_metadata["pages"] = pages
            if len(pages) == 1:
                chunk_metadata["page"] = pages[0]
        if paragraphs:
            chunk_metadata["paragraphs"] = paragraphs
        if block_types:
            chunk_metadata["block_types"] = block_types
        processed_chunks.append(
            DocumentChunk(
                content=chunk,
                chunk_index=index,
                start_char=chunk_start,
                end_char=chunk_end,
                metadata=chunk_metadata,
            )
        )
        start_char = chunk_end
    return processed_chunks


def _get_rag_plan(plan_key: Optional[str]) -> dict:
    return RAG_PLAN_PRESETS.get(
        (plan_key or "medium").lower(), RAG_PLAN_PRESETS["medium"]
    )


def _apply_rag_plan(kb: dict, plan_key: Optional[str]) -> None:
    plan = _get_rag_plan(plan_key)
    kb["rag_plan"] = plan["key"]
    kb["rag_mode"] = plan.get("rag_mode", "standard")
    kb["hardware_tier"] = plan["hardware_tier"]
    kb["embedding_provider"] = plan.get("embedding_provider")
    kb["embedding_model"] = plan["embedding_model"]
    kb["recommended_backend"] = plan.get("recommended_backend")
    kb["vector_backend"] = plan.get("vector_backend")
    kb["rag_architecture"] = plan.get("architecture")
    kb["splitter_config"] = plan["splitter_config"].copy()
    kb["retrieval_config"] = plan["retrieval_config"].copy()


def _plan_change_requires_reindex(kb: dict, next_plan_key: str) -> bool:
    return (
        kb.get("document_count", 0) > 0
        and (kb.get("rag_plan") or kb.get("hardware_tier") or "medium") != next_plan_key
    )


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    rag_plan: str = "medium"


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    embedding_model: str
    document_count: int = 0
    hardware_tier: Optional[str] = None
    rag_plan: Optional[str] = None
    rag_mode: Optional[str] = None
    embedding_provider: Optional[str] = None
    recommended_backend: Optional[str] = None
    vector_backend: Optional[str] = None
    rag_architecture: Optional[str] = None
    reindex_required: bool = False
    splitter_config: Optional[dict] = None
    retrieval_config: Optional[dict] = None
    datastore: Optional[dict] = None  # password in dsn is masked


class KnowledgeBaseDetailOut(KnowledgeBaseOut):
    documents: List[dict] = []


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    hardware_tier: Optional[str] = None
    rag_plan: Optional[str] = None
    reindex_required: Optional[bool] = None
    splitter_config: Optional[dict] = None
    retrieval_config: Optional[dict] = None
    datastore: Optional[dict] = None  # {"type": "pgvector", "dsn": "..."}


class KnowledgeBaseDocumentCreate(BaseModel):
    content: str
    metadata: Optional[dict] = None


class KnowledgeBaseHitTestRequest(BaseModel):
    query: str
    top_k: int = 5
    provider: Optional[str] = None
    model: Optional[str] = None


@router.get("/knowledge-bases", response_model=List[KnowledgeBaseOut])
async def list_knowledge_bases(user: dict = Depends(get_current_user)):
    """List all knowledge bases."""
    return [
        KnowledgeBaseOut(
            id=kb_id,
            name=kb["name"],
            description=kb.get("description"),
            embedding_model=kb.get("embedding_model", "text-embedding-3-small"),
            document_count=kb.get("document_count", 0),
            hardware_tier=kb.get("hardware_tier", "medium"),
            rag_plan=kb.get("rag_plan", kb.get("hardware_tier", "medium")),
            rag_mode=kb.get("rag_mode"),
            embedding_provider=kb.get("embedding_provider"),
            recommended_backend=kb.get("recommended_backend"),
            vector_backend=kb.get("vector_backend"),
            rag_architecture=kb.get("rag_architecture"),
            reindex_required=kb.get("reindex_required", False),
            splitter_config=kb.get("splitter_config"),
            retrieval_config=kb.get("retrieval_config"),
            datastore=_masked_datastore(kb),
        )
        for kb_id, kb in _knowledge_bases.items()
    ]


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate, user: dict = Depends(get_current_user)
):
    """Create a new knowledge base."""
    kb_id = str(uuid.uuid4())

    _knowledge_bases[kb_id] = {
        "name": payload.name,
        "description": payload.description,
        "embedding_model": payload.embedding_model,
        "document_count": 0,
        "reindex_required": False,
        "created_by": user.get("id", "unknown"),
    }
    _apply_rag_plan(_knowledge_bases[kb_id], payload.rag_plan)
    _persist_kb_state()

    return KnowledgeBaseOut(
        id=kb_id,
        name=payload.name,
        description=payload.description,
        embedding_model=_knowledge_bases[kb_id]["embedding_model"],
        document_count=0,
        hardware_tier=_knowledge_bases[kb_id]["hardware_tier"],
        rag_plan=_knowledge_bases[kb_id]["rag_plan"],
        rag_mode=_knowledge_bases[kb_id].get("rag_mode"),
        embedding_provider=_knowledge_bases[kb_id].get("embedding_provider"),
        recommended_backend=_knowledge_bases[kb_id].get("recommended_backend"),
        vector_backend=_knowledge_bases[kb_id].get("vector_backend"),
        rag_architecture=_knowledge_bases[kb_id].get("rag_architecture"),
        reindex_required=_knowledge_bases[kb_id].get("reindex_required", False),
        splitter_config=_knowledge_bases[kb_id]["splitter_config"],
        retrieval_config=_knowledge_bases[kb_id]["retrieval_config"],
        datastore=_masked_datastore(_knowledge_bases[kb_id]),
    )


@router.get("/knowledge-bases/rag-plans/presets")
async def list_rag_plan_presets(user: dict = Depends(get_current_user)):
    return {"data": list(RAG_PLAN_PRESETS.values())}


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseDetailOut)
async def get_knowledge_base(kb_id: str, user: dict = Depends(get_current_user)):
    """Get a knowledge base by ID."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    kb = _knowledge_bases[kb_id]
    return KnowledgeBaseDetailOut(
        id=kb_id,
        name=kb["name"],
        description=kb.get("description"),
        embedding_model=kb.get("embedding_model", "text-embedding-3-small"),
        document_count=kb.get("document_count", 0),
        hardware_tier=kb.get("hardware_tier", "medium"),
        rag_plan=kb.get("rag_plan", kb.get("hardware_tier", "medium")),
        rag_mode=kb.get("rag_mode"),
        embedding_provider=kb.get("embedding_provider"),
        recommended_backend=kb.get("recommended_backend"),
        vector_backend=kb.get("vector_backend"),
        rag_architecture=kb.get("rag_architecture"),
        reindex_required=kb.get("reindex_required", False),
        splitter_config=kb.get("splitter_config"),
        retrieval_config=kb.get("retrieval_config"),
        datastore=_masked_datastore(kb),
        documents=_knowledge_base_documents.get(kb_id, []),
    )


@router.put("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: str, payload: KnowledgeBaseUpdate, user: dict = Depends(get_current_user)
):
    """Update a knowledge base."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    kb = _knowledge_bases[kb_id]

    if payload.name is not None:
        kb["name"] = payload.name
    if payload.description is not None:
        kb["description"] = payload.description
    if payload.rag_plan is not None:
        next_plan = _get_rag_plan(payload.rag_plan)["key"]
        if _plan_change_requires_reindex(kb, next_plan):
            kb["reindex_required"] = True
        _apply_rag_plan(kb, next_plan)
    if payload.hardware_tier is not None:
        kb["hardware_tier"] = payload.hardware_tier
        kb["rag_plan"] = payload.hardware_tier
    if payload.splitter_config is not None:
        kb["splitter_config"] = payload.splitter_config
    if payload.retrieval_config is not None:
        kb["retrieval_config"] = payload.retrieval_config
    if payload.datastore is not None:
        store_type = payload.datastore.get("type")
        if not store_type:
            # Empty type means "follow plan/env": remove the KB-level override.
            kb.pop("datastore", None)
        else:
            if store_type not in {"sqlite", "pgvector", "elasticsearch"}:
                raise HTTPException(400, f"Unsupported datastore type: {store_type}")
            datastore = dict(payload.datastore)
            if store_type == "pgvector":
                if datastore.get("dsn"):
                    parse_pgvector_dsn(datastore["dsn"])  # validation
                if datastore.get("port") not in (None, ""):
                    try:
                        int(datastore["port"])
                    except (TypeError, ValueError):
                        raise HTTPException(400, "datastore port must be a number")
                stored = kb.get("datastore") or {}
                # The UI only ever sees masked secrets; keep stored values
                # when the payload omits them or sends the mask back.
                for secret_key in ("dsn", "password"):
                    incoming = datastore.get(secret_key)
                    if (not incoming or "****" in str(incoming)) and stored.get(
                        secret_key
                    ):
                        datastore[secret_key] = stored[secret_key]
            kb["datastore"] = datastore
    if payload.reindex_required is not None:
        kb["reindex_required"] = payload.reindex_required
    _persist_kb_state()

    return KnowledgeBaseOut(
        id=kb_id,
        name=kb["name"],
        description=kb.get("description"),
        embedding_model=kb.get("embedding_model", "text-embedding-3-small"),
        document_count=kb.get("document_count", 0),
        hardware_tier=kb.get("hardware_tier", "medium"),
        rag_plan=kb.get("rag_plan", kb.get("hardware_tier", "medium")),
        rag_mode=kb.get("rag_mode"),
        embedding_provider=kb.get("embedding_provider"),
        recommended_backend=kb.get("recommended_backend"),
        vector_backend=kb.get("vector_backend"),
        rag_architecture=kb.get("rag_architecture"),
        reindex_required=kb.get("reindex_required", False),
        splitter_config=kb.get("splitter_config"),
        retrieval_config=kb.get("retrieval_config"),
        datastore=_masked_datastore(kb),
    )


class DatastoreTestRequest(BaseModel):
    type: str
    dsn: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None


@router.post("/knowledge-bases/test-datastore")
async def test_datastore_connection(
    payload: DatastoreTestRequest, user: dict = Depends(get_current_user)
):
    """Test connectivity for a candidate datastore configuration."""
    from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

    config: dict = {}
    if payload.type == "pgvector":
        if payload.dsn:
            config = parse_pgvector_dsn(payload.dsn)
        else:
            config = {
                key: value
                for key, value in {
                    "host": payload.host,
                    "port": payload.port,
                    "user": payload.user,
                    "password": payload.password,
                    "database": payload.database,
                }.items()
                if value not in (None, "")
            }
    try:
        store = DataStoreFactory.create(store_type=payload.type, config=config)
        ok = await asyncio.to_thread(store.health_check)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Datastore connection failed: {exc}") from exc
    if not ok:
        raise HTTPException(400, "Datastore health check failed")
    return {"status": "ok", "type": payload.type}


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str, user: dict = Depends(get_current_user)):
    """Delete a knowledge base."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    datastore_config = _kb_datastore_config(kb_id)
    del _knowledge_bases[kb_id]
    if kb_id in _knowledge_base_documents:
        del _knowledge_base_documents[kb_id]
    _persist_kb_state()
    agent_index_service.clear_kb(kb_id)
    await asyncio.to_thread(
        agent_index_service.delete_index_collection, kb_id, datastore_config
    )

    return {"message": "Knowledge base deleted", "id": kb_id}


@router.post("/knowledge-bases/{kb_id}/documents")
async def add_document(
    kb_id: str,
    payload: KnowledgeBaseDocumentCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Add a document to a knowledge base."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    try:
        document_id = str(uuid.uuid4())
        doc_name = (payload.metadata or {}).get("name") or (
            f"Document {len(_knowledge_base_documents.get(kb_id, [])) + 1}"
        )
        splitter_config = _knowledge_bases[kb_id].get("splitter_config") or {}
        index_mode = splitter_config.get("index_mode") or "paragraph"
        if index_mode == "paragraph":
            splitter = SplitterFactory.create_from_dict(
                {
                    "type": splitter_config.get("type", "recursive"),
                    "chunk_size": splitter_config.get("chunk_size", 500),
                    "chunk_overlap": splitter_config.get("chunk_overlap", 100),
                }
            )
            split_chunks = splitter.split_text(payload.content)
            joined_text = payload.content
            source_chunk = DocumentChunk(
                content=payload.content,
                chunk_index=0,
                start_char=0,
                end_char=len(payload.content),
                metadata=payload.metadata or {},
            )
            processed_chunks = _map_split_chunks_to_metadata(
                split_chunks, [source_chunk], joined_text
            )
        else:
            processed_chunks = await asyncio.to_thread(
                _chunks_via_index_processor,
                index_mode,
                payload.content,
                payload.metadata or {},
                splitter_config,
            )

        # Stamp the document pointer on every chunk so agent-mode retrieval
        # can drill from an index-summary hit down to that document's chunks.
        for chunk in processed_chunks:
            chunk.metadata["document_id"] = document_id
            chunk.metadata.setdefault("document_name", doc_name)

        rag_level = _kb_resource_level(kb_id)
        rag_service = RAGService(
            resource_level=rag_level,
            config=_kb_datastore_config(kb_id),
        )
        await rag_service.add_documents(
            knowledge_base_id=kb_id,
            documents=processed_chunks,
        )

        _knowledge_bases[kb_id]["document_count"] = (
            _knowledge_bases[kb_id].get("document_count", 0) + 1
        )

        documents = _knowledge_base_documents.setdefault(kb_id, [])
        documents.append(
            {
                "id": document_id,
                "name": doc_name,
                "content_preview": payload.content[:120],
                "chunks": len(processed_chunks),
                "metadata": payload.metadata or {},
            }
        )
        _persist_kb_state()

        _schedule_agent_index(
            background_tasks, kb_id, document_id, doc_name, payload.content
        )

        return {
            "document_id": document_id,
            "chunks": len(processed_chunks),
            "status": "success",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-bases/{kb_id}/documents/upload")
async def upload_document(
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    suffix = Path(file.filename or "upload.txt").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        document_id = str(uuid.uuid4())
        doc_name = file.filename or f"Document {len(_knowledge_base_documents.get(kb_id, [])) + 1}"
        doc_processor = DocumentProcessor()
        processed = await doc_processor.process_file(tmp_path)
        joined_text = "\n\n".join(chunk.content for chunk in processed.chunks)
        splitter_config = _knowledge_bases[kb_id].get("splitter_config") or {}
        index_mode = splitter_config.get("index_mode") or "paragraph"
        if index_mode == "paragraph":
            splitter = SplitterFactory.create_from_dict(
                {
                    "type": splitter_config.get("type", "recursive"),
                    "chunk_size": splitter_config.get("chunk_size", 500),
                    "chunk_overlap": splitter_config.get("chunk_overlap", 100),
                }
            )
            split_chunks = splitter.split_text(joined_text)
            processed_chunks = _map_split_chunks_to_metadata(
                split_chunks, processed.chunks, joined_text
            )
        else:
            processed_chunks = await asyncio.to_thread(
                _chunks_via_index_processor,
                index_mode,
                joined_text,
                {"name": file.filename},
                splitter_config,
            )
        # Stamp the document pointer on every chunk (see add_document).
        for chunk in processed_chunks:
            chunk.metadata["document_id"] = document_id
            chunk.metadata.setdefault("document_name", doc_name)

        rag_service = RAGService(
            resource_level=_kb_resource_level(kb_id),
            config=_kb_datastore_config(kb_id),
        )
        await rag_service.add_documents(
            knowledge_base_id=kb_id,
            documents=processed_chunks,
        )

        _knowledge_bases[kb_id]["document_count"] = (
            _knowledge_bases[kb_id].get("document_count", 0) + 1
        )
        documents = _knowledge_base_documents.setdefault(kb_id, [])
        documents.append(
            {
                "id": document_id,
                "name": doc_name,
                "content_preview": processed_chunks[0].content[:120]
                if processed_chunks
                else "",
                "chunks": len(processed_chunks),
                "metadata": {"source": "upload", "file_type": suffix},
            }
        )
        _persist_kb_state()
        _schedule_agent_index(
            background_tasks, kb_id, document_id, doc_name, joined_text
        )
        return {
            "document_id": document_id,
            "chunks": len(processed_chunks),
            "status": "success",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


@router.get("/knowledge-bases/{kb_id}/documents")
async def list_documents(kb_id: str, user: dict = Depends(get_current_user)):
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"data": _knowledge_base_documents.get(kb_id, [])}


@router.post("/knowledge-bases/{kb_id}/hit-test")
async def hit_test_knowledge_base(
    kb_id: str,
    payload: KnowledgeBaseHitTestRequest,
    user: dict = Depends(get_current_user),
):
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    if not payload.provider:
        raise HTTPException(400, "请选择模型提供商或先添加供应商。")
    if not payload.model:
        raise HTTPException(400, "请选择要调用的模型。")
    active = model_provider_service.get_active_provider_config(payload.provider)
    if not active:
        raise HTTPException(400, f"Provider '{payload.provider}' is not configured")
    credentials = active.get("credentials", {}) if active else {}
    rag_service = RAGService(
        resource_level=_kb_resource_level(kb_id),
        config={
            **_kb_datastore_config(kb_id),
            "retrieval_config": _knowledge_bases.get(kb_id, {}).get("retrieval_config")
            or {},
            "llm_provider": payload.provider,
            "llm_model": payload.model,
            "api_key": credentials.get("api_key"),
            "base_url": credentials.get("base_url"),
        },
    )
    try:
        response = await rag_service.query(
            query=payload.query,
            knowledge_base_id=kb_id,
            top_k=payload.top_k,
            conversation_id="hit-test",
        )
        return {
            "answer": response.answer,
            "sources": [
                {
                    "content": source.content,
                    "score": source.score,
                    "metadata": source.metadata,
                }
                for source in response.sources
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/knowledge-bases/{kb_id}/documents/{document_id}")
async def delete_document(
    kb_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    documents = _knowledge_base_documents.get(kb_id, [])
    filtered = [doc for doc in documents if doc["id"] != document_id]
    if len(filtered) == len(documents):
        raise HTTPException(status_code=404, detail="Document not found")
    _knowledge_base_documents[kb_id] = filtered
    _knowledge_bases[kb_id]["document_count"] = len(filtered)
    _persist_kb_state()
    # Agent 模式：移除索引条目并后台重建索引集合，避免已删文档的摘要继续被路由命中。
    kb = _knowledge_bases[kb_id]
    if kb.get("rag_mode") == "agent":
        agent_index_service.remove_entry(kb_id, document_id)
        llm_config = resolve_default_llm_config()
        if llm_config is not None:
            background_tasks.add_task(
                agent_index_service.resync_collection,
                kb_id,
                {**_kb_datastore_config(kb_id), **llm_config},
                _kb_resource_level(kb_id),
            )
    return {"result": "success"}


@router.get("/knowledge-bases/{kb_id}/agent-index")
async def get_agent_index(kb_id: str, user: dict = Depends(get_current_user)):
    """List agent-mode index entries (title/summary/keywords/status per document)."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    kb = _knowledge_bases[kb_id]
    return {
        "data": agent_index_service.list_entries(kb_id),
        "rag_mode": kb.get("rag_mode", "standard"),
    }


@router.post("/knowledge-bases/{kb_id}/agent-index/rebuild")
async def rebuild_agent_index(
    kb_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Regenerate all agent index entries of a KB in the background."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    kb = _knowledge_bases[kb_id]
    if kb.get("rag_mode") != "agent":
        raise HTTPException(400, "该知识库不是 Agent 主动检索方案")
    llm_config = resolve_default_llm_config()
    if llm_config is None:
        raise HTTPException(400, "未配置默认模型供应商，无法生成 Agent 索引")
    documents = [
        {"id": doc.get("id"), "name": doc.get("name")}
        for doc in _knowledge_base_documents.get(kb_id, [])
    ]
    for doc in documents:
        if doc.get("id"):
            agent_index_service.upsert_entry(
                kb_id, doc["id"], name=doc.get("name"), status="pending", error=None
            )
    background_tasks.add_task(
        agent_index_service.rebuild_kb,
        kb_id,
        documents,
        {**_kb_datastore_config(kb_id), **llm_config},
        _kb_resource_level(kb_id),
    )
    return {"status": "rebuilding", "documents": len(documents)}
