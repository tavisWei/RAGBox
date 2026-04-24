"""RAG service integrating embedding, retrieval, and LLM."""

import asyncio
import os
from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional, Dict, Any

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
from api.core.rag.retrieval.multi_way_retriever import MultiWayRetriever
from api.core.rag.retrieval.retrieval_config import RetrievalConfig


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
            "db_path": "data/rag_data.db",
            "vector_enabled": default_config.get("vector_enabled", True),
        }
        if "vector_enabled" in self.config:
            datastore_config["vector_enabled"] = self.config["vector_enabled"]
        datastore_config.update(self.config.get("datastore", {}))
        self.data_store = DataStoreFactory.create(
            store_type=store_type,
            config=datastore_config,
        )

        self.top_k = default_config.get("max_documents", 10)
        self.use_reranker = default_config.get("rerank_enabled", False)

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

        def llm_fn(prompt: str) -> str:
            return ""

        retriever = MultiWayRetriever(
            data_store=self.data_store,
            config=retrieval_config,
            llm_function=llm_fn,
        )

        try:
            results = retriever.retrieve(
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
            docs = []

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

        response = await self.llm_service.chat(
            messages=messages,
            config=ChatConfig(
                system_prompt=final_system_prompt,
                max_tokens=1024,
                temperature=0.7,
            ),
        )
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
        response = await self.query(
            query=query,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            conversation_id=conversation_id,
            use_reranker=use_reranker,
            system_prompt=system_prompt,
        )

        for chunk in response.answer.split():
            yield chunk + " "

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
        for doc in documents:
            try:
                embedding = await self.embedding_service.embed_single(doc.content)
            except Exception:
                embedding = [0.0] * 1536

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

        self.data_store.create_collection(knowledge_base_id)
        self.data_store.add_documents(
            collection_name=knowledge_base_id,
            documents=documents_to_store,
            embeddings=embeddings_to_store,
        )


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
