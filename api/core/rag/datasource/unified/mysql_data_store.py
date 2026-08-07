"""MySQL data store backed by PyMySQL (optional dependency).

Vectors are stored as float32 BLOBs and scored in Python (numpy cosine), the
same version-agnostic strategy as the SQLite store; full-text uses a MySQL
FULLTEXT index with the ngram parser (CJK-capable) and falls back to LIKE.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .base_data_store import BaseDataStore, DataStoreStats, Document, SearchResult
from .exceptions import CollectionNotFoundError, ConfigurationError, DataStoreError


class MySQLDataStore(BaseDataStore):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import pymysql  # noqa: F401
        except ImportError as exc:
            raise ConfigurationError(
                "pymysql is required for MySQLDataStore. "
                "Install it with: pip install pymysql"
            ) from exc
        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", 3306))
        self.user = config.get("user", "root")
        self.password = config.get("password", "")
        self.database = config.get("database", "rag_platform")

    def _get_backend_type(self) -> str:
        return "mysql"

    def _table(self, collection_name: str) -> str:
        safe = "".join(
            char if char.isalnum() or char == "_" else "_" for char in collection_name
        )
        return f"rag_{safe}"

    def _connect(self):
        import pymysql

        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
        )

    # ------------------------------------------------------------------
    # BaseDataStore interface
    # ------------------------------------------------------------------
    def create_collection(
        self, collection_name: str, dimension: Optional[int] = None
    ) -> None:
        table = self._table(collection_name)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS `{table}` (
                            id VARCHAR(64) PRIMARY KEY,
                            content MEDIUMTEXT,
                            metadata JSON,
                            embedding BLOB,
                            created_at VARCHAR(40),
                            FULLTEXT INDEX `ft_{table}` (content) WITH PARSER ngram
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                        """
                    )
                except Exception:
                    # ngram parser unavailable (older MySQL/MariaDB): plain table.
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS `{table}` (
                            id VARCHAR(64) PRIMARY KEY,
                            content MEDIUMTEXT,
                            metadata JSON,
                            embedding BLOB,
                            created_at VARCHAR(40)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                        """
                    )
            conn.commit()
        finally:
            conn.close()

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        import json
        import uuid
        from datetime import datetime

        table = self._table(collection_name)
        doc_ids: List[str] = []
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for i, doc in enumerate(documents):
                    doc_id = doc.metadata.get("doc_id") or str(uuid.uuid4())
                    doc_ids.append(doc_id)
                    blob = None
                    if embeddings is not None:
                        blob = np.array(embeddings[i], dtype=np.float32).tobytes()
                    cur.execute(
                        f"REPLACE INTO `{table}` (id, content, metadata, embedding, created_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (
                            doc_id,
                            doc.page_content,
                            json.dumps(doc.metadata, ensure_ascii=False),
                            blob,
                            datetime.utcnow().isoformat(),
                        ),
                    )
            conn.commit()
        finally:
            conn.close()
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
                self._vector_search(collection_name, query_vector, top_k, score_threshold)
            )
        if search_method in ("keyword", "fulltext", "hybrid"):
            results.extend(self._fulltext_search(collection_name, query, top_k))
        return self._deduplicate_and_sort(results, top_k)

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        if not doc_ids:
            return
        table = self._table(collection_name)
        placeholders = ",".join("%s" for _ in doc_ids)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM `{table}` WHERE id IN ({placeholders})", tuple(doc_ids)
                )
            conn.commit()
        finally:
            conn.close()

    def delete_collection(self, collection_name: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS `{self._table(collection_name)}`")
            conn.commit()
        finally:
            conn.close()

    def get_stats(self, collection_name: str) -> DataStoreStats:
        table = self._table(collection_name)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                count = int(cur.fetchone()[0])
            return DataStoreStats(
                total_documents=count,
                total_chunks=count,
                index_size_bytes=0,
                avg_query_latency_ms=0.0,
                backend_type=self.backend_type,
            )
        finally:
            conn.close()

    def health_check(self) -> bool:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                conn.close()
        except Exception:
            return False

    def list_documents(self, collection_name: str) -> List[Dict[str, Any]]:
        import json

        table = self._table(collection_name)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT id, content, metadata FROM `{table}`")
                rows = cur.fetchall()
            return [
                {
                    "doc_id": row[0],
                    "content": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_documents_by_ids(
        self, collection_name: str, doc_ids: List[str]
    ) -> List[SearchResult]:
        import json

        if not doc_ids:
            return []
        table = self._table(collection_name)
        placeholders = ",".join("%s" for _ in doc_ids)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, content, metadata FROM `{table}` WHERE id IN ({placeholders})",
                    tuple(doc_ids),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        by_id = {row[0]: row for row in rows}
        return [
            SearchResult(
                content=by_id[doc_id][1],
                score=0.0,
                doc_id=doc_id,
                metadata=json.loads(by_id[doc_id][2]) if by_id[doc_id][2] else {},
                retrieval_method="keyword",
            )
            for doc_id in doc_ids
            if doc_id in by_id
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _vector_search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int,
        score_threshold: float,
    ) -> List[SearchResult]:
        import json

        table = self._table(collection_name)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, content, metadata, embedding FROM `{table}` "
                    "WHERE embedding IS NOT NULL"
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        query = np.array(query_vector, dtype=np.float32)
        query_norm = float(np.linalg.norm(query))
        results: List[SearchResult] = []
        for row in rows:
            embedding = np.frombuffer(row[3], dtype=np.float32)
            denom = query_norm * float(np.linalg.norm(embedding))
            if denom == 0:
                continue
            score = float(np.dot(query, embedding) / denom)
            if score >= score_threshold:
                results.append(
                    SearchResult(
                        content=row[1],
                        score=score,
                        doc_id=row[0],
                        metadata=json.loads(row[2]) if row[2] else {},
                        retrieval_method="semantic",
                    )
                )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _fulltext_search(
        self, collection_name: str, query: str, top_k: int
    ) -> List[SearchResult]:
        import json

        if not query.strip():
            return []
        table = self._table(collection_name)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                rows: List[Any] = []
                try:
                    cur.execute(
                        f"SELECT id, content, metadata, "
                        f"MATCH(content) AGAINST (%s IN NATURAL LANGUAGE MODE) AS score "
                        f"FROM `{table}` "
                        f"WHERE MATCH(content) AGAINST (%s IN NATURAL LANGUAGE MODE) "
                        f"ORDER BY score DESC LIMIT %s",
                        (query, query, top_k),
                    )
                    rows = list(cur.fetchall())
                except Exception:
                    rows = []
                if not rows:
                    cur.execute(
                        f"SELECT id, content, metadata, NULL FROM `{table}` "
                        "WHERE content LIKE %s LIMIT %s",
                        (f"%{query}%", top_k),
                    )
                    rows = list(cur.fetchall())
        finally:
            conn.close()

        return [
            SearchResult(
                content=row[1],
                score=float(row[3]) if row[3] is not None else 0.5,
                doc_id=row[0],
                metadata=json.loads(row[2]) if row[2] else {},
                retrieval_method="fulltext",
            )
            for row in rows
        ]

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
