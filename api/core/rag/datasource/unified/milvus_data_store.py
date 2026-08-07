"""Milvus data store backed by pymilvus (optional dependency)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_data_store import BaseDataStore, DataStoreStats, Document, SearchResult
from .exceptions import CollectionNotFoundError, ConfigurationError, DataStoreError


class MilvusDataStore(BaseDataStore):
    """Milvus backend: cosine vector search + LIKE-based full-text fallback."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            from pymilvus import connections, utility  # noqa: F401
        except ImportError as exc:
            raise ConfigurationError(
                "pymilvus is required for MilvusDataStore. "
                "Install it with: pip install pymilvus"
            ) from exc
        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", 19530))
        self.alias = "rag-default"
        connections.connect(alias=self.alias, host=self.host, port=self.port)

    def _get_backend_type(self) -> str:
        return "milvus"

    # ------------------------------------------------------------------
    # BaseDataStore interface
    # ------------------------------------------------------------------
    def create_collection(
        self, collection_name: str, dimension: Optional[int] = None
    ) -> None:
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility

        if utility.has_collection(collection_name):
            return
        dim = dimension or 1536
        fields = [
            FieldSchema(
                name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64
            ),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        collection = Collection(
            name=collection_name, schema=CollectionSchema(fields)
        )
        collection.create_index(
            field_name="embedding",
            index_params={
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 64},
            },
        )

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        import uuid

        from pymilvus import Collection

        if embeddings is None or len(embeddings) != len(documents):
            raise DataStoreError(
                "Milvus backend requires embeddings for every document"
            )
        collection = Collection(collection_name)
        doc_ids = [doc.metadata.get("doc_id") or str(uuid.uuid4()) for doc in documents]
        collection.insert(
            [
                doc_ids,
                [doc.page_content for doc in documents],
                [doc.metadata for doc in documents],
                list(embeddings),
            ]
        )
        collection.flush()
        return doc_ids

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
        from pymilvus import Collection, utility

        if not utility.has_collection(collection_name):
            raise CollectionNotFoundError(
                f"Collection '{collection_name}' not found"
            )
        collection = Collection(collection_name)
        collection.load()
        try:
            results: List[SearchResult] = []
            if search_method in ("semantic", "hybrid") and query_vector:
                hits = collection.search(
                    data=[query_vector],
                    anns_field="embedding",
                    param={"metric_type": "COSINE", "params": {"ef": 64}},
                    limit=top_k,
                    output_fields=["content", "metadata"],
                )[0]
                for hit in hits:
                    score = float(hit.score)
                    if score >= score_threshold:
                        entity = hit.entity
                        results.append(
                            SearchResult(
                                content=entity.get("content"),
                                score=score,
                                doc_id=str(hit.id),
                                metadata=entity.get("metadata") or {},
                                retrieval_method="semantic",
                            )
                        )
            if search_method in ("keyword", "fulltext", "hybrid") and query.strip():
                rows = collection.query(
                    expr=f'content like "%{query}%"',
                    output_fields=["id", "content", "metadata"],
                    limit=top_k,
                )
                for row in rows:
                    results.append(
                        SearchResult(
                            content=row.get("content", ""),
                            score=0.5,
                            doc_id=str(row.get("id")),
                            metadata=row.get("metadata") or {},
                            retrieval_method="fulltext",
                        )
                    )
            return self._deduplicate_and_sort(results, top_k)
        finally:
            collection.release()

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        if not doc_ids:
            return
        from pymilvus import Collection

        collection = Collection(collection_name)
        quoted = ",".join(f'"{doc_id}"' for doc_id in doc_ids)
        collection.delete(expr=f"id in [{quoted}]")

    def delete_collection(self, collection_name: str) -> None:
        from pymilvus import utility

        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)

    def get_stats(self, collection_name: str) -> DataStoreStats:
        from pymilvus import Collection, utility

        if not utility.has_collection(collection_name):
            raise CollectionNotFoundError(
                f"Collection '{collection_name}' not found"
            )
        collection = Collection(collection_name)
        count = collection.num_entities
        return DataStoreStats(
            total_documents=count,
            total_chunks=count,
            index_size_bytes=0,
            avg_query_latency_ms=0.0,
            backend_type=self.backend_type,
        )

    def health_check(self) -> bool:
        try:
            from pymilvus import connections

            return connections.has_connection(self.alias)
        except Exception:
            return False

    def list_documents(self, collection_name: str) -> List[Dict[str, Any]]:
        from pymilvus import Collection

        collection = Collection(collection_name)
        collection.load()
        try:
            rows = collection.query(
                expr="id >= ''",
                output_fields=["id", "content", "metadata"],
                limit=10000,
            )
            return [
                {
                    "doc_id": str(row.get("id")),
                    "content": row.get("content", ""),
                    "metadata": row.get("metadata") or {},
                }
                for row in rows
            ]
        finally:
            collection.release()

    def get_documents_by_ids(
        self, collection_name: str, doc_ids: List[str]
    ) -> List[SearchResult]:
        if not doc_ids:
            return []
        from pymilvus import Collection

        collection = Collection(collection_name)
        collection.load()
        try:
            quoted = ",".join(f'"{doc_id}"' for doc_id in doc_ids)
            rows = collection.query(
                expr=f"id in [{quoted}]",
                output_fields=["id", "content", "metadata"],
                limit=len(doc_ids),
            )
            by_id = {str(row.get("id")): row for row in rows}
            return [
                SearchResult(
                    content=by_id[doc_id].get("content", ""),
                    score=0.0,
                    doc_id=doc_id,
                    metadata=by_id[doc_id].get("metadata") or {},
                    retrieval_method="keyword",
                )
                for doc_id in doc_ids
                if doc_id in by_id
            ]
        finally:
            collection.release()

    @staticmethod
    def _deduplicate_and_sort(
        results: List[SearchResult], top_k: int
    ) -> List[SearchResult]:
        seen = set()
        deduplicated = []
        for result in results:
            key = result.doc_id or result.content
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(result)
        deduplicated.sort(key=lambda r: r.score, reverse=True)
        return deduplicated[:top_k]
