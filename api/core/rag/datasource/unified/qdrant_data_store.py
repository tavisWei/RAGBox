"""Qdrant data store backed by the Qdrant REST API (no extra dependency)."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from .base_data_store import BaseDataStore, DataStoreStats, Document, SearchResult
from .exceptions import CollectionNotFoundError, ConfigurationError, DataStoreError

# Cap for scroll-based listings (list_documents).
_SCROLL_PAGE_LIMIT = 1000


class QdrantDataStore(BaseDataStore):
    """Qdrant backend: cosine vector search + payload full-text match."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = str(config.get("url") or "http://localhost:6333").rstrip("/")
        self.api_key = config.get("api_key") or ""
        self.timeout = float(config.get("timeout", 10.0))
        self._client = httpx.Client(
            base_url=self.url,
            headers={"api-key": self.api_key} if self.api_key else None,
            timeout=self.timeout,
        )
        self.health_check()

    def _get_backend_type(self) -> str:
        return "qdrant"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DataStoreError(f"Qdrant request failed: {exc}") from exc
        if response.status_code == 404:
            raise CollectionNotFoundError(f"Qdrant resource not found: {path}")
        if response.status_code >= 400:
            raise DataStoreError(
                f"Qdrant {method} {path} -> {response.status_code}: {response.text[:300]}"
            )
        payload = response.json()
        return payload.get("result", payload)

    # ------------------------------------------------------------------
    # BaseDataStore interface
    # ------------------------------------------------------------------
    def create_collection(
        self, collection_name: str, dimension: Optional[int] = None
    ) -> None:
        dim = dimension or 1536
        try:
            self._request("GET", f"/collections/{collection_name}")
            return
        except CollectionNotFoundError:
            pass
        self._request(
            "PUT",
            f"/collections/{collection_name}",
            json={"vectors": {"size": dim, "distance": "Cosine"}},
        )
        # Full-text index on the content payload for the keyword leg.
        try:
            self._request(
                "PUT",
                f"/collections/{collection_name}/index",
                json={"field_name": "content", "field_schema": "text"},
            )
        except DataStoreError:
            # Older Qdrant versions may reject the text index; full-text leg
            # then simply matches nothing instead of breaking ingestion.
            pass

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        import uuid

        points = []
        doc_ids: List[str] = []
        for i, doc in enumerate(documents):
            doc_id = doc.metadata.get("doc_id") or str(uuid.uuid4())
            doc_ids.append(doc_id)
            vector = embeddings[i] if embeddings else None
            if vector is None:
                raise DataStoreError(
                    "Qdrant backend requires embeddings for every document"
                )
            points.append(
                {
                    "id": doc_id,
                    "vector": vector,
                    "payload": {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                    },
                }
            )
        if points:
            self._request(
                "PUT",
                f"/collections/{collection_name}/points",
                params={"wait": "true"},
                json={"points": points},
            )
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
        results: List[SearchResult] = []
        if search_method in ("semantic", "hybrid") and query_vector:
            results.extend(
                self._vector_search(
                    collection_name, query_vector, top_k, score_threshold, filters
                )
            )
        if search_method in ("keyword", "fulltext", "hybrid"):
            results.extend(
                self._fulltext_search(collection_name, query, top_k, filters)
            )
        return self._deduplicate_and_sort(results, top_k)

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        if not doc_ids:
            return
        self._request(
            "POST",
            f"/collections/{collection_name}/points/delete",
            params={"wait": "true"},
            json={"points": doc_ids},
        )

    def delete_collection(self, collection_name: str) -> None:
        try:
            self._request("DELETE", f"/collections/{collection_name}")
        except CollectionNotFoundError:
            pass

    def get_stats(self, collection_name: str) -> DataStoreStats:
        info = self._request("GET", f"/collections/{collection_name}")
        count = int(info.get("points_count") or 0)
        return DataStoreStats(
            total_documents=count,
            total_chunks=count,
            index_size_bytes=0,
            avg_query_latency_ms=0.0,
            backend_type=self.backend_type,
        )

    def health_check(self) -> bool:
        try:
            self._request("GET", "/collections")
            return True
        except Exception:
            return False

    def list_documents(self, collection_name: str) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        offset: Any = None
        while True:
            body: Dict[str, Any] = {
                "limit": _SCROLL_PAGE_LIMIT,
                "with_payload": True,
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            result = self._request(
                "POST", f"/collections/{collection_name}/points/scroll", json=body
            )
            for point in result.get("points", []):
                payload = point.get("payload") or {}
                documents.append(
                    {
                        "doc_id": point.get("id"),
                        "content": payload.get("content", ""),
                        "metadata": payload.get("metadata") or {},
                    }
                )
            offset = result.get("next_page_offset")
            if offset is None:
                return documents

    def get_documents_by_ids(
        self, collection_name: str, doc_ids: List[str]
    ) -> List[SearchResult]:
        if not doc_ids:
            return []
        points = self._request(
            "POST",
            f"/collections/{collection_name}/points",
            json={"ids": doc_ids, "with_payload": True, "with_vector": False},
        )
        by_id = {}
        for point in points:
            payload = point.get("payload") or {}
            by_id[str(point.get("id"))] = SearchResult(
                content=payload.get("content", ""),
                score=0.0,
                doc_id=str(point.get("id")),
                metadata=payload.get("metadata") or {},
                retrieval_method="keyword",
            )
        return [by_id[doc_id] for doc_id in doc_ids if doc_id in by_id]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _vector_search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        body: Dict[str, Any] = {
            "vector": query_vector,
            "limit": top_k,
            "with_payload": True,
            "score_threshold": score_threshold or None,
        }
        if filters:
            body["filter"] = {
                "must": [
                    {"key": f"metadata.{key}", "match": {"value": value}}
                    for key, value in filters.items()
                ]
            }
        started = time.time()
        result = self._request(
            "POST", f"/collections/{collection_name}/points/search", json=body
        )
        _ = started  # latency hook kept simple; stats report 0 for now
        return [
            SearchResult(
                content=(point.get("payload") or {}).get("content", ""),
                score=float(point.get("score") or 0.0),
                doc_id=str(point.get("id")),
                metadata=(point.get("payload") or {}).get("metadata") or {},
                retrieval_method="semantic",
            )
            for point in result
        ]

    def _fulltext_search(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        if not query.strip():
            return []
        must: List[Dict[str, Any]] = [
            {"key": "content", "match": {"text": query}}
        ]
        if filters:
            must.extend(
                {"key": f"metadata.{key}", "match": {"value": value}}
                for key, value in filters.items()
            )
        try:
            result = self._request(
                "POST",
                f"/collections/{collection_name}/points/scroll",
                json={
                    "limit": top_k,
                    "filter": {"must": must},
                    "with_payload": True,
                    "with_vector": False,
                },
            )
        except DataStoreError:
            return []
        results = []
        # Scroll has no relevance scoring; rank by query occurrence count.
        for point in result.get("points", []):
            payload = point.get("payload") or {}
            content = payload.get("content", "")
            results.append(
                SearchResult(
                    content=content,
                    score=float(content.count(query)) or 0.5,
                    doc_id=str(point.get("id")),
                    metadata=payload.get("metadata") or {},
                    retrieval_method="fulltext",
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results

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
