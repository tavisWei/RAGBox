from abc import ABC, abstractmethod
from typing import Any, List, Optional

from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.models.document import AttachmentDocument, Document
from api.core.rag.index_processor.constant.index_type import IndexTechniqueType


class BaseIndexProcessor(ABC):
    @abstractmethod
    def extract(self, extract_setting: ExtractSetting, **kwargs) -> List[Document]:
        raise NotImplementedError

    @abstractmethod
    def transform(self, documents: List[Document], **kwargs) -> List[Document]:
        raise NotImplementedError

    @abstractmethod
    def load(self, dataset_id: str, documents: List[Document], **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared concrete helpers backed by a unified data store. Processors
    # receive the store (and precomputed embeddings) via kwargs, e.g.
    # load(..., data_store=store, embeddings=[[...], ...]).
    # ------------------------------------------------------------------
    @staticmethod
    def _to_store_documents(
        dataset_id: str, documents: List[Document]
    ) -> List[Any]:
        from api.core.rag.datasource.unified.base_data_store import (
            Document as StoreDocument,
        )

        return [
            StoreDocument(
                page_content=doc.page_content,
                metadata={
                    **(doc.metadata or {}),
                    "knowledge_base_id": dataset_id,
                },
            )
            for doc in documents
        ]

    def _load_to_store(
        self,
        dataset_id: str,
        documents: List[Document],
        data_store,
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        store_docs = self._to_store_documents(dataset_id, documents)
        dimension = len(embeddings[0]) if embeddings else None
        data_store.create_collection(dataset_id, dimension=dimension)
        return data_store.add_documents(dataset_id, store_docs, embeddings)

    @staticmethod
    def _clean_from_store(
        dataset_id: str, data_store, node_ids: Optional[List[str]] = None
    ) -> None:
        if node_ids:
            data_store.delete_documents(dataset_id, node_ids)
        else:
            data_store.delete_collection(dataset_id)

    @staticmethod
    def _retrieve_from_store(
        query: str,
        dataset_id: str,
        top_k: int,
        data_store,
        query_vector: Optional[List[float]] = None,
        search_method: str = "hybrid",
    ) -> List[Document]:
        results = data_store.search(
            collection_name=dataset_id,
            query=query,
            query_vector=query_vector,
            top_k=top_k,
            search_method=search_method,
        )
        return [
            Document(
                page_content=result.content,
                vector=query_vector,
                metadata={**result.metadata, "score": result.score},
            )
            for result in results
        ]
