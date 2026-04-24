from __future__ import annotations

import json
import uuid
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


class PGVectorDataStore(BaseDataStore):
    """
    PostgreSQL + pgvector data storage adapter.

    Suitable for medium-resource scenarios.
    Uses pgvector extension for vector storage and HNSW indexing.
    Uses PostgreSQL tsvector for fulltext search.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.user = config.get("user", "postgres")
        self.password = config.get("password", "")
        self.database = config.get("database", "dify")
        self._pool = None
        self._init_extensions()

    def _get_backend_type(self) -> str:
        return "pgvector"

    def _get_connection(self):
        """Get a database connection."""
        try:
            import psycopg2
            from psycopg2 import pool
        except ImportError as exc:
            raise ConfigurationError(
                "psycopg2 is required for PGVectorDataStore. "
                "Install it with: pip install psycopg2-binary"
            ) from exc

        if self._pool is None:
            self._pool = pool.SimpleConnectionPool(
                1,
                10,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
            )
        return self._pool.getconn()

    def _release_connection(self, conn):
        """Release a connection back to the pool."""
        if self._pool is not None:
            self._pool.putconn(conn)

    def _init_extensions(self) -> None:
        """Initialize required PostgreSQL extensions."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                conn.commit()
        except Exception as exc:
            raise ConfigurationError(
                f"Failed to initialize pgvector extensions: {exc}"
            ) from exc
        finally:
            self._release_connection(conn)

    def create_collection(
        self, collection_name: str, dimension: Optional[int] = None
    ) -> None:
        """Create a collection (table + indexes) for storing documents."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Create documents table with embedding column
                dim = dimension or 1536
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {collection_name}_docs (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector({dim}),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Create GIN index on metadata for filtering
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{collection_name}_metadata
                    ON {collection_name}_docs USING GIN (metadata)
                    """
                )

                # Create tsvector GIN index for fulltext search
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{collection_name}_fts
                    ON {collection_name}_docs
                    USING GIN (to_tsvector('simple', content))
                    """
                )

                # Create HNSW index for vector similarity search
                if dimension:
                    cur.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{collection_name}_vector
                        ON {collection_name}_docs
                        USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64)
                        """
                    )

                conn.commit()
        except Exception as exc:
            raise IndexingError(
                f"Failed to create collection '{collection_name}': {exc}"
            ) from exc
        finally:
            self._release_connection(conn)

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        """Add documents to the collection."""
        doc_ids: List[str] = []
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                for i, doc in enumerate(documents):
                    doc_id = doc.metadata.get("doc_id", str(uuid.uuid4()))
                    doc_ids.append(doc_id)
                    embedding = embeddings[i] if embeddings else None

                    cur.execute(
                        f"""
                        INSERT INTO {collection_name}_docs (id, content, metadata, embedding)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                        """,
                        (
                            doc_id,
                            doc.page_content,
                            json.dumps(doc.metadata),
                            embedding,
                        ),
                    )

                conn.commit()
        except Exception as exc:
            raise IndexingError(
                f"Failed to add documents to collection '{collection_name}': {exc}"
            ) from exc
        finally:
            self._release_connection(conn)

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
        results: List[SearchResult] = []

        if search_method in ("keyword", "fulltext", "hybrid"):
            results.extend(
                self._fulltext_search(
                    collection_name, query, top_k, score_threshold, filters
                )
            )

        if search_method in ("semantic", "hybrid") and query_vector:
            results.extend(
                self._vector_search(
                    collection_name, query_vector, top_k, score_threshold, filters
                )
            )

        return self._deduplicate_and_sort(results, top_k)

    def _fulltext_search(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        """Perform fulltext search using PostgreSQL tsvector."""
        results: List[SearchResult] = []
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Build filter clause if filters provided
                filter_clause = ""
                filter_params: List[Any] = []
                if filters:
                    conditions = []
                    for key, value in filters.items():
                        conditions.append(f"metadata @> %s")
                        filter_params.append(json.dumps({key: value}))
                    if conditions:
                        filter_clause = "AND " + " AND ".join(conditions)

                cur.execute(
                    f"""
                    SELECT
                        id,
                        content,
                        metadata,
                        ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', %s)) as score
                    FROM {collection_name}_docs
                    WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
                    {filter_clause}
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (query, query) + tuple(filter_params) + (top_k,),
                )

                for row in cur:
                    score = float(row[3])
                    if score >= score_threshold:
                        results.append(
                            SearchResult(
                                content=row[1],
                                score=score,
                                doc_id=row[0],
                                metadata=row[2] or {},
                                retrieval_method="fulltext",
                            )
                        )
        except Exception as exc:
            if "does not exist" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise
        finally:
            self._release_connection(conn)

        return results

    def _vector_search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        """Perform vector similarity search using pgvector."""
        results: List[SearchResult] = []
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Build filter clause if filters provided
                filter_clause = ""
                filter_params: List[Any] = []
                if filters:
                    conditions = []
                    for key, value in filters.items():
                        conditions.append(f"metadata @> %s")
                        filter_params.append(json.dumps({key: value}))
                    if conditions:
                        filter_clause = "AND " + " AND ".join(conditions)

                cur.execute(
                    f"""
                    SELECT
                        id,
                        content,
                        metadata,
                        1 - (embedding <=> %s::vector) as score
                    FROM {collection_name}_docs
                    WHERE embedding IS NOT NULL
                    {filter_clause}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector,) + tuple(filter_params) + (query_vector, top_k),
                )

                for row in cur:
                    score = float(row[3])
                    if score >= score_threshold:
                        results.append(
                            SearchResult(
                                content=row[1],
                                score=score,
                                doc_id=row[0],
                                metadata=row[2] or {},
                                retrieval_method="vector",
                            )
                        )
        except Exception as exc:
            if "does not exist" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise
        finally:
            self._release_connection(conn)

        return results

    def _deduplicate_and_sort(
        self, results: List[SearchResult], top_k: int
    ) -> List[SearchResult]:
        """Deduplicate results by doc_id and sort by score descending."""
        seen: set = set()
        unique_results: List[SearchResult] = []
        for r in results:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                unique_results.append(r)
        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:top_k]

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        """Delete documents by their IDs."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.executemany(
                    f"DELETE FROM {collection_name}_docs WHERE id = %s",
                    [(doc_id,) for doc_id in doc_ids],
                )
                conn.commit()
        except Exception as exc:
            if "does not exist" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise
        finally:
            self._release_connection(conn)

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection (drops the table)."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {collection_name}_docs CASCADE")
                conn.commit()
        finally:
            self._release_connection(conn)

    def get_stats(self, collection_name: str) -> DataStoreStats:
        """Get collection statistics."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {collection_name}_docs")
                total_docs = cur.fetchone()[0]

                cur.execute(
                    f"""
                    SELECT pg_total_relation_size('{collection_name}_docs')
                    """
                )
                size_result = cur.fetchone()
                index_size = size_result[0] if size_result else 0

                return DataStoreStats(
                    total_documents=total_docs,
                    total_chunks=total_docs,
                    index_size_bytes=index_size,
                    avg_query_latency_ms=0.0,
                    backend_type="pgvector",
                )
        except Exception as exc:
            if "does not exist" in str(exc):
                raise CollectionNotFoundError(
                    f"Collection '{collection_name}' not found"
                ) from exc
            raise
        finally:
            self._release_connection(conn)

    def health_check(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            self._release_connection(conn)
            return True
        except Exception:
            return False
