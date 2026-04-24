from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    page_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    content: str
    score: float
    doc_id: str
    metadata: Dict[str, Any]
    retrieval_method: str


@dataclass
class DataStoreStats:
    total_documents: int
    total_chunks: int
    index_size_bytes: int
    avg_query_latency_ms: float
    backend_type: str


class BaseDataStore(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backend_type = self._get_backend_type()

    @abstractmethod
    def _get_backend_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def create_collection(self, collection_name: str, dimension: Optional[int] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
        search_method: str = "hybrid",
    ) -> List[SearchResult]:
        raise NotImplementedError

    @abstractmethod
    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_stats(self, collection_name: str) -> DataStoreStats:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError
