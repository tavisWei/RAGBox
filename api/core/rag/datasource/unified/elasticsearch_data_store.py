from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from api.core.rag.datasource.unified.base_data_store import (
    BaseDataStore,
    DataStoreStats,
    Document,
    SearchResult,
)
from api.core.rag.datasource.unified.exceptions import (
    CollectionNotFoundError,
    ConfigurationError,
    IndexingError,
)


class ElasticsearchDataStore(BaseDataStore):
    """
    Elasticsearch data storage adapter.

    Suitable for high-resource scenarios with large-scale data.
    Supports native hybrid search using BM25 + dense_vector with RRF.
    Uses Elasticsearch 8.x API.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.hosts = config.get("hosts", ["http://localhost:9200"])
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.api_key = config.get("api_key", "")
        self.verify_certs = config.get("verify_certs", True)
        self._es = None
        self._connect()

    def _get_backend_type(self) -> str:
        return "elasticsearch"

    def _connect(self) -> None:
        """Establish connection to Elasticsearch cluster."""
        try:
            from elasticsearch import Elasticsearch
        except ImportError as exc:
            raise ConfigurationError(
                "elasticsearch-py is required for ElasticsearchDataStore. "
                "Install it with: pip install elasticsearch"
            ) from exc

        conn_kwargs: Dict[str, Any] = {
            "hosts": self.hosts,
            "verify_certs": self.verify_certs,
        }

        if self.api_key:
            conn_kwargs["api_key"] = self.api_key
        elif self.username and self.password:
            conn_kwargs["basic_auth"] = (self.username, self.password)

        self._es = Elasticsearch(**conn_kwargs)

    def _get_es(self):
        """Get the Elasticsearch client, reconnecting if needed."""
        if self._es is None:
            self._connect()
        return self._es

    def create_collection(
        self, collection_name: str, dimension: Optional[int] = None
    ) -> None:
        """Create an Elasticsearch index with appropriate mappings."""
        es = self._get_es()
        dim = dimension or 1536

        mapping = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": "standard",
                    },
                    "metadata": {
                        "type": "object",
                        "dynamic": True,
                    },
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dim,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "created_at": {
                        "type": "date",
                    },
                }
            },
        }

        try:
            if not es.indices.exists(index=collection_name):
                es.indices.create(index=collection_name, body=mapping)
        except Exception as exc:
            raise IndexingError(
                f"Failed to create index '{collection_name}': {exc}"
            ) from exc

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        """Add documents to the Elasticsearch index."""
        es = self._get_es()
        doc_ids: List[str] = []

        try:
            for i, doc in enumerate(documents):
                doc_id = doc.metadata.get("doc_id", str(uuid.uuid4()))
                doc_ids.append(doc_id)

                body = {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "created_at": datetime.utcnow().isoformat(),
                }

                if embeddings:
                    body["embedding"] = embeddings[i]

                es.index(index=collection_name, id=doc_id, body=body)

            es.indices.refresh(index=collection_name)
        except Exception as exc:
            raise IndexingError(
                f"Failed to add documents to index '{collection_name}': {exc}"
            ) from exc

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
        """Search documents using the specified method."""
        if search_method == "semantic" and query_vector:
            return self._vector_search(
                collection_name, query_vector, top_k, score_threshold, filters
            )
        elif search_method in ("keyword", "fulltext"):
            return self._fulltext_search(
                collection_name, query, top_k, score_threshold, filters
            )
        elif search_method == "hybrid" and query_vector:
            return self._hybrid_search_rrf(
                collection_name, query, query_vector, top_k, score_threshold, filters
            )
        else:
            # Default to fulltext search
            return self._fulltext_search(
                collection_name, query, top_k, score_threshold, filters
            )

    def _build_filter_clause(
        self, filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Build an Elasticsearch filter clause from metadata filters."""
        if not filters:
            return None

        must_clauses = []
        for key, value in filters.items():
            must_clauses.append({"term": {f"metadata.{key}": value}})

        return {"bool": {"filter": must_clauses}}

    def _vector_search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        """Perform pure vector search using kNN."""
        es = self._get_es()

        body: Dict[str, Any] = {
            "knn": {
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": top_k * 2,
            },
            "size": top_k,
        }

        filter_clause = self._build_filter_clause(filters)
        if filter_clause:
            body["knn"]["filter"] = filter_clause

        try:
            response = es.search(index=collection_name, body=body)
            return self._parse_results(response, "vector", score_threshold)
        except Exception as exc:
            if "index_not_found_exception" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise

    def _fulltext_search(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        """Perform pure fulltext search using BM25."""
        es = self._get_es()

        query_clause = {"match": {"content": query}}
        filter_clause = self._build_filter_clause(filters)

        if filter_clause:
            body = {
                "query": {
                    "bool": {
                        "must": [query_clause],
                        "filter": filter_clause["bool"]["filter"],
                    }
                },
                "size": top_k,
            }
        else:
            body = {
                "query": query_clause,
                "size": top_k,
            }

        try:
            response = es.search(index=collection_name, body=body)
            return self._parse_results(response, "fulltext", score_threshold)
        except Exception as exc:
            if "index_not_found_exception" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise

    def _hybrid_search_rrf(
        self,
        collection_name: str,
        query: str,
        query_vector: List[float],
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        """
        Perform hybrid search using Elasticsearch native RRF.

        ES 8.x supports RRF by combining a standard query with kNN search
        and using the `rank` parameter with `rrf`.
        """
        es = self._get_es()

        query_clause = {"match": {"content": query}}
        filter_clause = self._build_filter_clause(filters)

        if filter_clause:
            body = {
                "query": {
                    "bool": {
                        "must": [query_clause],
                        "filter": filter_clause["bool"]["filter"],
                    }
                },
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 2,
                },
                "rank": {
                    "rrf": {
                        "window_size": top_k * 2,
                        "rank_constant": 60,
                    }
                },
                "size": top_k,
            }
        else:
            body = {
                "query": query_clause,
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 2,
                },
                "rank": {
                    "rrf": {
                        "window_size": top_k * 2,
                        "rank_constant": 60,
                    }
                },
                "size": top_k,
            }

        try:
            response = es.search(index=collection_name, body=body)
            return self._parse_results(response, "hybrid", score_threshold)
        except Exception as exc:
            if "index_not_found_exception" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise

    def _parse_results(
        self,
        response: Dict[str, Any],
        retrieval_method: str,
        score_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """Parse Elasticsearch search response into SearchResult objects."""
        results: List[SearchResult] = []
        hits = response.get("hits", {}).get("hits", [])

        for hit in hits:
            score = hit.get("_score", 0.0)
            if score is None:
                score = 0.0
            if score < score_threshold:
                continue

            source = hit.get("_source", {})
            results.append(
                SearchResult(
                    content=source.get("content", ""),
                    score=float(score),
                    doc_id=hit.get("_id", ""),
                    metadata=source.get("metadata", {}),
                    retrieval_method=retrieval_method,
                )
            )

        return results

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        """Delete documents by their IDs."""
        es = self._get_es()
        try:
            for doc_id in doc_ids:
                es.delete(index=collection_name, id=doc_id, ignore=[404])
        except Exception as exc:
            if "index_not_found_exception" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise

    def delete_collection(self, collection_name: str) -> None:
        """Delete an Elasticsearch index."""
        es = self._get_es()
        es.indices.delete(index=collection_name, ignore=[404])

    def get_stats(self, collection_name: str) -> DataStoreStats:
        """Get index statistics."""
        es = self._get_es()
        try:
            stats = es.indices.stats(index=collection_name)
            index_stats = (
                stats.get("indices", {}).get(collection_name, {}).get("total", {})
            )

            doc_count = index_stats.get("docs", {}).get("count", 0)
            store_size = index_stats.get("store", {}).get("size_in_bytes", 0)

            return DataStoreStats(
                total_documents=doc_count,
                total_chunks=doc_count,
                index_size_bytes=store_size,
                avg_query_latency_ms=0.0,
                backend_type="elasticsearch",
            )
        except Exception as exc:
            if "index_not_found_exception" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise

    def health_check(self) -> bool:
        """Check if Elasticsearch cluster is reachable."""
        try:
            es = self._get_es()
            return es.ping()
        except Exception:
            return False
