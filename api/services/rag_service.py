"""RAG service integrating embedding, retrieval, and LLM."""

import asyncio
import os
from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional, Dict, Any
from urllib.parse import unquote, urlparse

from api.services.embedding_service import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingService,
    EmbeddingResult,
)
from api.services.llm_service import (
    LLMService,
    ChatMessage,
    ChatCompletion,
    ChatConfig,
)
from api.services.document_processor import DocumentChunk
from api.services.resource_config_service import ResourceConfigService, ResourceLevel
from api.core.rag.datasource.unified.base_data_store import Document
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory
from api.core.rag.index_processor.processor.parent_child_index_processor import (
    collapse_parent_child_docs,
)
from api.core.rag.retrieval.multi_way_retriever import MultiWayRetriever
from api.core.rag.retrieval.retrieval_config import RerankMode, RetrievalConfig


def parse_pgvector_dsn(dsn: str) -> Dict[str, Any]:
    """Parse a SQLAlchemy-style DSN into PGVectorDataStore config fields.

    The store driver is psycopg2 regardless of the scheme's driver suffix
    (e.g. postgresql+asyncpg:// works fine).
    """
    parsed = urlparse(dsn)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or "postgres"),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/") or "postgres",
    }


def _pgvector_config_from_env() -> Dict[str, Any]:
    """Build PGVectorDataStore config from PGVECTOR_DSN / PGVECTOR_* env vars."""
    dsn = os.getenv("PGVECTOR_DSN")
    if dsn:
        return parse_pgvector_dsn(dsn)
    if os.getenv("PGVECTOR_HOST") or os.getenv("PGVECTOR_DATABASE"):
        return {
            "host": os.getenv("PGVECTOR_HOST", "localhost"),
            "port": int(os.getenv("PGVECTOR_PORT", "5432")),
            "user": os.getenv("PGVECTOR_USER", "postgres"),
            "password": os.getenv("PGVECTOR_PASSWORD", ""),
            "database": os.getenv("PGVECTOR_DATABASE", "postgres"),
        }
    return {}


# In-memory jieba keyword indexes, one per knowledge base. Rebuilt lazily
# from the data store after a process restart.
_keyword_tables: Dict[str, Any] = {}


def _new_keyword_table():
    from api.core.rag.keyword.keyword_table_handler import KeywordTableHandler

    return KeywordTableHandler()


def _get_keyword_table(data_store, knowledge_base_id: str):
    handler = _keyword_tables.get(knowledge_base_id)
    if handler is not None:
        return handler
    try:
        docs = data_store.list_documents(knowledge_base_id)
    except Exception:
        return None
    if not docs:
        return None
    try:
        handler = _new_keyword_table()
        handler.add_documents({d["doc_id"]: d["content"] for d in docs})
    except Exception:
        # jieba unavailable or extraction failed: keyword leg stays off.
        return None
    _keyword_tables[knowledge_base_id] = handler
    return handler


@dataclass
class RAGSource:
    """Source document in RAG response."""

    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResponse:
    """Response from RAG service."""

    answer: str
    sources: List[RAGSource]
    conversation_id: str
    tokens_used: Optional[int] = None


class RAGService:
    """Complete RAG service combining embedding, retrieval, and LLM."""

    def __init__(
        self,
        resource_level: ResourceLevel = ResourceLevel.MEDIUM,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize RAG service.

        Args:
            resource_level: LOW, MEDIUM, or HIGH
            config: Optional override configuration
        """
        self.resource_level = resource_level
        self.config = config or {}

        default_config = ResourceConfigService.get_default_config(resource_level)

        embedding_provider = self.config.get("embedding_provider") or os.getenv(
            "EMBEDDING_PROVIDER", "huggingface"
        )
        embedding_model = self.config.get("embedding_model") or os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        llm_provider = self.config.get("llm_provider")
        llm_model = self.config.get("llm_model")
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url")

        embedding_config = EmbeddingConfig(
            provider=EmbeddingProvider(embedding_provider),
            model_name=embedding_model,
            api_key=self.config.get("embedding_api_key") or api_key,
            api_base=self.config.get("embedding_api_base") or base_url,
            ollama_host=self.config.get("ollama_host", "http://localhost:11434"),
        )
        self.embedding_service = EmbeddingService(embedding_config)
        self.embedding_service._provider = self.embedding_service._create_provider(
            embedding_config
        )
        if not llm_provider:
            raise ValueError("请选择模型提供商或先添加供应商。")
        if not llm_model:
            raise ValueError("请选择要调用的模型。")
        self.llm_service = LLMService(
            provider=llm_provider,
            model=llm_model,
            api_key=api_key,
            base_url=base_url,
        )

        store_type = (
            self.config.get("data_store_type")
            or default_config.get("data_store_type")
            or os.getenv("DATA_STORE_TYPE")
            or "sqlite"
        )
        datastore_config = {
            "db_path": "api/data/rag.sqlite",
            "vector_enabled": default_config.get("vector_enabled", True),
        }
        if "vector_enabled" in self.config:
            datastore_config["vector_enabled"] = self.config["vector_enabled"]
        if store_type == "pgvector":
            datastore_config.update(_pgvector_config_from_env())
        datastore_config.update(self.config.get("datastore", {}))
        self.data_store = DataStoreFactory.create(
            store_type=store_type,
            config=datastore_config,
        )

        self.top_k = default_config.get("max_documents", 10)
        self.use_reranker = default_config.get("rerank_enabled", False)

    async def _retrieve_docs(
        self,
        query: str,
        knowledge_base_id: str,
        top_k: int,
        use_reranker: bool,
    ) -> List[Dict[str, Any]]:
        """Embed the query and run multi-way retrieval.

        The retriever is synchronous and may call the LLM (query expansion /
        listwise rerank) through a synchronous function, so retrieval runs in
        a worker thread; the llm bridge spins a throwaway event loop there,
        which is legal because that thread has no running loop.
        """
        try:
            query_embedding = await self.embedding_service.embed_single(query)
        except Exception:
            query_embedding = None

        retrieval_config_dict = self.config.get("retrieval_config") or {}
        retrieval_config = (
            RetrievalConfig.from_dict(retrieval_config_dict)
            if retrieval_config_dict
            else RetrievalConfig.intermediate()
        )
        if not use_reranker:
            retrieval_config.rerank_mode = RerankMode.NONE

        def llm_fn(prompt: str) -> str:
            response = asyncio.run(
                self.llm_service.chat(
                    messages=[ChatMessage(role="user", content=prompt)],
                    config=ChatConfig(max_tokens=1024, temperature=0.0),
                )
            )
            return response.content

        def keyword_search(collection_name: str, query_text: str, limit: int):
            handler = _get_keyword_table(self.data_store, collection_name)
            if handler is None:
                return []
            doc_ids = handler.search(query_text, top_k=limit)
            results = self.data_store.get_documents_by_ids(collection_name, doc_ids)
            for rank, result in enumerate(results):
                result.score = 1.0 / (rank + 1)
                result.retrieval_method = "keyword"
            return results

        retriever = MultiWayRetriever(
            data_store=self.data_store,
            config=retrieval_config,
            llm_function=llm_fn,
            keyword_search=keyword_search,
        )

        try:
            results = await asyncio.to_thread(
                retriever.retrieve,
                collection_name=knowledge_base_id,
                query=query,
                query_vector=query_embedding,
                top_k=top_k,
            )
            docs = [
                {"content": r.content, "score": r.score, "metadata": r.metadata}
                for r in results
            ]
        except Exception:
            return []
        # Parent-child indexing stores child chunks; map hits back to the
        # parent passage (no-op for docs without parent metadata).
        return collapse_parent_child_docs(docs)

    @staticmethod
    def _build_messages(
        query: str,
        docs: List[Dict[str, Any]],
        knowledge_base_id: str,
        system_prompt: Optional[str],
    ) -> tuple[List[ChatMessage], ChatConfig]:
        if not docs:
            context = f"知识库 '{knowledge_base_id}' 中没有找到相关文档。"
        else:
            context_parts = []
            for i, doc in enumerate(docs[:3], 1):
                content = doc.get("content", str(doc))[:500]
                context_parts.append(f"[文档 {i}]: {content}")
            context = "\n\n".join(context_parts)

        messages = [ChatMessage(role="user", content=query)]
        base_prompt = system_prompt or "你是一个专业的AI助手。"
        final_system_prompt = f"""{base_prompt}

基于以下上下文信息回答用户的问题。

上下文:
{context}

请根据上下文信息回答问题。如果上下文中没有相关信息，请如实说明。"""
        return messages, ChatConfig(
            system_prompt=final_system_prompt,
            max_tokens=1024,
            temperature=0.7,
        )

    async def query(
        self,
        query: str,
        knowledge_base_id: str,
        top_k: int = 5,
        conversation_id: Optional[str] = None,
        use_reranker: bool = True,
        system_prompt: Optional[str] = None,
    ) -> RAGResponse:
        """
        Query the RAG system and get an answer.

        Args:
            query: User query
            knowledge_base_id: Knowledge base to search
            top_k: Number of documents to retrieve
            conversation_id: Optional conversation ID for context
            use_reranker: Whether to use reranking

        Returns:
            RAGResponse with answer and sources
        """
        docs = await self._retrieve_docs(query, knowledge_base_id, top_k, use_reranker)
        messages, config = self._build_messages(
            query, docs, knowledge_base_id, system_prompt
        )
        response = await self.llm_service.chat(messages=messages, config=config)
        answer = response.content

        sources = []
        for doc in docs[:top_k]:
            sources.append(
                RAGSource(
                    content=str(doc.get("content", ""))[:500],
                    score=doc.get("score", 0.0),
                    metadata=doc.get("metadata", {}),
                )
            )

        return RAGResponse(
            answer=answer,
            sources=sources,
            conversation_id=conversation_id or "",
        )

    async def query_stream(
        self,
        query: str,
        knowledge_base_id: str,
        top_k: int = 5,
        conversation_id: Optional[str] = None,
        use_reranker: bool = True,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Query the RAG system with streaming response.

        Args:
            query: User query
            knowledge_base_id: Knowledge base to search
            top_k: Number of documents to retrieve
            conversation_id: Optional conversation ID
            use_reranker: Whether to use reranking

        Yields:
            Response chunks as strings
        """
        docs = await self._retrieve_docs(query, knowledge_base_id, top_k, use_reranker)
        messages, config = self._build_messages(
            query, docs, knowledge_base_id, system_prompt
        )
        async for chunk in self.llm_service.chat_stream(
            messages=messages, config=config
        ):
            yield chunk

    async def add_documents(
        self,
        knowledge_base_id: str,
        documents: List[DocumentChunk],
    ) -> None:
        """
        Add documents to a knowledge base.

        Args:
            knowledge_base_id: Target knowledge base
            documents: List of document chunks to add
        """
        documents_to_store: List[Document] = []
        embeddings_to_store: List[List[float]] = []
        # Zero-vector fallback must match the provider's dimension, otherwise
        # pgvector's typed vector(dim) column rejects the row.
        fallback_dim = 1536 if self.embedding_service.config.provider == EmbeddingProvider.OPENAI else 768
        for doc in documents:
            try:
                embedding = await self.embedding_service.embed_single(doc.content)
            except Exception:
                embedding = [0.0] * fallback_dim

            documents_to_store.append(
                Document(
                    page_content=doc.content,
                    metadata={
                        **doc.metadata,
                        "knowledge_base_id": knowledge_base_id,
                        "chunk_index": doc.chunk_index,
                    },
                )
            )
            embeddings_to_store.append(embedding)

        # Pass the real dimension so backends can build typed vector columns
        # and ANN indexes (pgvector only creates the HNSW index when the
        # dimension is explicit).
        dimension = len(embeddings_to_store[0]) if embeddings_to_store else None
        self.data_store.create_collection(knowledge_base_id, dimension=dimension)
        doc_ids = self.data_store.add_documents(
            collection_name=knowledge_base_id,
            documents=documents_to_store,
            embeddings=embeddings_to_store,
        )

        # Keep the per-KB jieba keyword index in sync.
        try:
            handler = _keyword_tables.get(knowledge_base_id) or _new_keyword_table()
            for doc_id, doc in zip(doc_ids, documents):
                handler.add_document(doc_id=doc_id, text=doc.content)
            _keyword_tables[knowledge_base_id] = handler
        except Exception:
            # jieba unavailable: keyword leg stays off for this KB.
            _keyword_tables.pop(knowledge_base_id, None)


def create_rag_service(
    resource_level: str = "medium",
    **kwargs,
) -> RAGService:
    """
    Factory function to create RAG service.

    Args:
        resource_level: "low", "medium", or "high"
        **kwargs: Additional configuration

    Returns:
        Configured RAGService instance
    """
    level = ResourceLevel(resource_level.lower())
    return RAGService(resource_level=level, config=kwargs)
