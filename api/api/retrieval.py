"""Retrieval routes with real RAG service integration."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid

from api.services.rag_service import RAGService
from api.services.document_processor import DocumentProcessor
from api.services.knowledge_base_store import knowledge_base_store
from api.services.resource_config_service import ResourceLevel
from api.services.model_provider_service import model_provider_service
from api.core.rag.retrieval.retrieval_config import RetrievalConfig
from .deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Global RAG service instance (initialized on first request)
_rag_service: Optional[RAGService] = None
_document_processor: Optional[DocumentProcessor] = None
RETRIEVAL_QUERY_TIMEOUT_SECONDS = 60


def get_rag_service() -> RAGService:
    """Get or create RAG service instance."""
    global _rag_service
    if _rag_service is None:
        raise ValueError("请选择模型提供商和模型后再发起问答。")
    return _rag_service


def build_rag_service(
    knowledge_base_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> RAGService:
    if not provider:
        raise ValueError("请选择模型提供商或先添加供应商。")
    if not model:
        raise ValueError("请选择要调用的模型。")
    config: Dict[str, Any] = {"data_store_type": "sqlite"}
    kb = {}
    if knowledge_base_id:
        kb = (
            knowledge_base_store.read_all()
            .get("knowledge_bases", {})
            .get(knowledge_base_id, {})
        )
        if kb.get("retrieval_config"):
            config["retrieval_config"] = kb.get("retrieval_config")
    active = model_provider_service.get_active_provider_config(provider)
    if not active:
        raise ValueError(f"Provider '{provider}' is not configured")
    credentials = active.get("credentials", {})
    config.update(
        {
            "llm_provider": provider,
            "llm_model": model,
            "api_key": credentials.get("api_key"),
            "base_url": credentials.get("base_url"),
        }
    )
    tier = (kb.get("hardware_tier") or "medium").lower()
    level = (
        ResourceLevel.LOW
        if tier == "low"
        else ResourceLevel.HIGH
        if tier == "high"
        else ResourceLevel.MEDIUM
    )
    return RAGService(resource_level=level, config=config)


def get_kb_retrieval_config(knowledge_base_id: str) -> Dict[str, Any]:
    store = knowledge_base_store.read_all()
    kb = store.get("knowledge_bases", {}).get(knowledge_base_id, {})
    return kb.get("retrieval_config", {})


def get_document_processor() -> DocumentProcessor:
    """Get or create document processor instance."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


class RetrieveRequest(BaseModel):
    query: str
    knowledge_base_id: str
    top_k: int = 5
    filters: Optional[dict] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class RetrieveResult(BaseModel):
    content: str
    score: float
    metadata: dict


class RetrieveResponse(BaseModel):
    query: str
    results: List[RetrieveResult]


class ChatRequest(BaseModel):
    query: str
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: Optional[List[str]] = None
    conversation_id: Optional[str] = None
    top_k: int = 5
    provider: Optional[str] = None
    model: Optional[str] = None


class QARequest(BaseModel):
    question: str
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: Optional[List[str]] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[RetrieveResult]
    conversation_id: str


class UploadDocumentRequest(BaseModel):
    knowledge_base_id: str
    file_type: str = "txt"


class UploadDocumentResponse(BaseModel):
    document_id: str
    chunks: int
    status: str


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(payload: RetrieveRequest, user: dict = Depends(get_current_user)):
    """Retrieve relevant documents from a knowledge base."""
    kb_ids = payload.knowledge_base_ids or [payload.knowledge_base_id]
    rag_service = build_rag_service(kb_ids[0], payload.provider, payload.model)
    retrieval_config = get_kb_retrieval_config(kb_ids[0])
    effective_top_k = retrieval_config.get("top_k", payload.top_k)

    try:
        response = await rag_service.query(
            query=payload.query,
            knowledge_base_id=payload.knowledge_base_id,
            top_k=effective_top_k,
        )

        results = [
            RetrieveResult(
                content=source.content,
                score=source.score,
                metadata=source.metadata,
            )
            for source in response.sources
        ]

        return RetrieveResponse(query=payload.query, results=results)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, user: dict = Depends(get_current_user)):
    """Chat with the RAG system."""
    kb_ids = payload.knowledge_base_ids or [payload.knowledge_base_id or "default"]

    conversation_id = payload.conversation_id or str(uuid.uuid4())

    try:
        responses = []
        for kb_id in kb_ids:
            retrieval_config = get_kb_retrieval_config(kb_id)
            effective_top_k = retrieval_config.get("top_k", payload.top_k)
            rag_service = build_rag_service(kb_id, payload.provider, payload.model)
            responses.append(
                await asyncio.wait_for(
                    rag_service.query(
                        query=payload.query,
                        knowledge_base_id=kb_id,
                        top_k=effective_top_k,
                        conversation_id=conversation_id,
                    ),
                    timeout=RETRIEVAL_QUERY_TIMEOUT_SECONDS,
                )
            )
        response = responses[0]

        return ChatResponse(
            answer="\n\n".join(item.answer for item in responses),
            sources=[
                RetrieveResult(
                    content=source.content,
                    score=source.score,
                    metadata=source.metadata,
                )
                for source in response.sources
            ],
            conversation_id=response.conversation_id,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa")
async def qa(payload: QARequest, user: dict = Depends(get_current_user)):
    """QA endpoint - main chat interface for the frontend."""
    conversation_id = str(uuid.uuid4())
    kb_ids = payload.knowledge_base_ids or [payload.knowledge_base_id or "default"]

    try:
        responses = []
        response_configs = []
        for kb_id in kb_ids:
            retrieval_config = get_kb_retrieval_config(kb_id)
            response_configs.append(retrieval_config)
            effective_top_k = retrieval_config.get("top_k", 5)
            rag_service = build_rag_service(kb_id, payload.provider, payload.model)
            responses.append(
                await asyncio.wait_for(
                    rag_service.query(
                        query=payload.question,
                        knowledge_base_id=kb_id,
                        top_k=effective_top_k,
                        conversation_id=conversation_id,
                    ),
                    timeout=RETRIEVAL_QUERY_TIMEOUT_SECONDS,
                )
            )
        response = responses[0]

        return {
            "success": True,
            "data": {
                "answer": "\n\n".join(item.answer for item in responses),
                "sources": [
                    {
                        "content": source.content,
                        "score": source.score,
                        "metadata": source.metadata,
                    }
                    for source in response.sources
                ],
                "conversation_id": response.conversation_id,
                "retrieval_config": response_configs[0] if response_configs else {},
                "retrieval_configs": response_configs,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/stream")
async def qa_stream(payload: QARequest, user: dict = Depends(get_current_user)):
    kb_ids = payload.knowledge_base_ids or [payload.knowledge_base_id or "default"]

    async def event_stream():
        try:
            for kb_id in kb_ids:
                retrieval_config = get_kb_retrieval_config(kb_id)
                effective_top_k = retrieval_config.get("top_k", 5)
                rag_service = build_rag_service(kb_id, payload.provider, payload.model)
                async for chunk in rag_service.query_stream(
                    query=payload.question,
                    knowledge_base_id=kb_id,
                    top_k=effective_top_k,
                    conversation_id=str(uuid.uuid4()),
                    system_prompt="你是一个专业的AI助手。",
                ):
                    yield chunk
                if len(kb_ids) > 1 and kb_id != kb_ids[-1]:
                    yield "\n\n"
        except Exception as exc:
            logger.exception("QA stream failed")
            if isinstance(exc, ValueError):
                yield f"Error: {str(exc)}"
            else:
                yield "Error: 请求处理失败，请稍后重试。"

    return StreamingResponse(event_stream(), media_type="text/plain")


@router.post("/upload")
async def upload_document(
    knowledge_base_id: str,
    content: str,
    metadata: Optional[dict] = None,
    user: dict = Depends(get_current_user),
):
    """Upload a document to a knowledge base."""
    rag_service = get_rag_service()
    doc_processor = get_document_processor()

    try:
        processed = await doc_processor.process_text(
            text=content,
            metadata=None,
        )

        await rag_service.add_documents(
            knowledge_base_id=knowledge_base_id,
            documents=processed.chunks,
        )

        return UploadDocumentResponse(
            document_id=str(uuid.uuid4()),
            chunks=len(processed.chunks),
            status="success",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConfigPresetResponse(BaseModel):
    name: str
    config: Dict[str, Any]


@router.get("/retrieval/config-presets", response_model=List[ConfigPresetResponse])
async def get_config_presets():
    """Get available retrieval configuration presets."""
    presets = [
        ConfigPresetResponse(
            name="beginner",
            config=RetrievalConfig.beginner().to_dict(),
        ),
        ConfigPresetResponse(
            name="intermediate",
            config=RetrievalConfig.intermediate().to_dict(),
        ),
        ConfigPresetResponse(
            name="advanced",
            config=RetrievalConfig.advanced().to_dict(),
        ),
        ConfigPresetResponse(
            name="expert",
            config=RetrievalConfig.expert().to_dict(),
        ),
    ]
    return presets
