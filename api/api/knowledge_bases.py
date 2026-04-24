"""Knowledge base routes with real storage integration."""

import os
import uuid

import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional

from api.services.document_processor import DocumentProcessor, DocumentChunk
from api.services.knowledge_base_store import knowledge_base_store
from api.services.model_provider_service import model_provider_service
from api.services.rag_service import RAGService
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


def _kb_datastore_config(kb_id: str) -> dict:
    kb = _knowledge_bases.get(kb_id, {})
    plan = _get_rag_plan(kb.get("rag_plan"))
    runtime_store = (
        os.getenv("DATA_STORE_TYPE") or plan.get("recommended_backend") or "sqlite"
    )
    return {
        "data_store_type": runtime_store,
        "vector_enabled": plan.get("hardware_tier") != "low"
        or plan.get("vector_backend") == "sqlite-builtin",
        "embedding_provider": kb.get("embedding_provider")
        or plan.get("embedding_provider"),
        "embedding_model": kb.get("embedding_model") or plan.get("embedding_model"),
    }


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
    embedding_provider: Optional[str] = None
    recommended_backend: Optional[str] = None
    vector_backend: Optional[str] = None
    rag_architecture: Optional[str] = None
    reindex_required: bool = False
    splitter_config: Optional[dict] = None
    retrieval_config: Optional[dict] = None


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
            embedding_provider=kb.get("embedding_provider"),
            recommended_backend=kb.get("recommended_backend"),
            vector_backend=kb.get("vector_backend"),
            rag_architecture=kb.get("rag_architecture"),
            reindex_required=kb.get("reindex_required", False),
            splitter_config=kb.get("splitter_config"),
            retrieval_config=kb.get("retrieval_config"),
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
        embedding_provider=_knowledge_bases[kb_id].get("embedding_provider"),
        recommended_backend=_knowledge_bases[kb_id].get("recommended_backend"),
        vector_backend=_knowledge_bases[kb_id].get("vector_backend"),
        rag_architecture=_knowledge_bases[kb_id].get("rag_architecture"),
        reindex_required=_knowledge_bases[kb_id].get("reindex_required", False),
        splitter_config=_knowledge_bases[kb_id]["splitter_config"],
        retrieval_config=_knowledge_bases[kb_id]["retrieval_config"],
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
        embedding_provider=kb.get("embedding_provider"),
        recommended_backend=kb.get("recommended_backend"),
        vector_backend=kb.get("vector_backend"),
        rag_architecture=kb.get("rag_architecture"),
        reindex_required=kb.get("reindex_required", False),
        splitter_config=kb.get("splitter_config"),
        retrieval_config=kb.get("retrieval_config"),
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
        embedding_provider=kb.get("embedding_provider"),
        recommended_backend=kb.get("recommended_backend"),
        vector_backend=kb.get("vector_backend"),
        rag_architecture=kb.get("rag_architecture"),
        reindex_required=kb.get("reindex_required", False),
        splitter_config=kb.get("splitter_config"),
        retrieval_config=kb.get("retrieval_config"),
    )


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str, user: dict = Depends(get_current_user)):
    """Delete a knowledge base."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    del _knowledge_bases[kb_id]
    if kb_id in _knowledge_base_documents:
        del _knowledge_base_documents[kb_id]
    _persist_kb_state()

    return {"message": "Knowledge base deleted", "id": kb_id}


@router.post("/knowledge-bases/{kb_id}/documents")
async def add_document(
    kb_id: str,
    payload: KnowledgeBaseDocumentCreate,
    user: dict = Depends(get_current_user),
):
    """Add a document to a knowledge base."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    try:
        splitter_config = _knowledge_bases[kb_id].get("splitter_config") or {}
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

        document_id = str(uuid.uuid4())
        documents = _knowledge_base_documents.setdefault(kb_id, [])
        documents.append(
            {
                "id": document_id,
                "name": (payload.metadata or {}).get("name")
                or f"Document {len(documents) + 1}",
                "content_preview": payload.content[:120],
                "chunks": len(processed_chunks),
                "metadata": payload.metadata or {},
            }
        )
        _persist_kb_state()

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
        doc_processor = DocumentProcessor()
        processed = await doc_processor.process_file(tmp_path)
        splitter_config = _knowledge_bases[kb_id].get("splitter_config") or {}
        splitter = SplitterFactory.create_from_dict(
            {
                "type": splitter_config.get("type", "recursive"),
                "chunk_size": splitter_config.get("chunk_size", 500),
                "chunk_overlap": splitter_config.get("chunk_overlap", 100),
            }
        )
        joined_text = "\n\n".join(chunk.content for chunk in processed.chunks)
        split_chunks = splitter.split_text(joined_text)
        processed_chunks = _map_split_chunks_to_metadata(
            split_chunks, processed.chunks, joined_text
        )
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
        document_id = str(uuid.uuid4())
        documents = _knowledge_base_documents.setdefault(kb_id, [])
        documents.append(
            {
                "id": document_id,
                "name": file.filename or f"Document {len(documents) + 1}",
                "content_preview": processed_chunks[0].content[:120]
                if processed_chunks
                else "",
                "chunks": len(processed_chunks),
                "metadata": {"source": "upload", "file_type": suffix},
            }
        )
        _persist_kb_state()
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
    kb_id: str, document_id: str, user: dict = Depends(get_current_user)
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
    return {"result": "success"}
