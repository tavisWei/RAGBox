from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

import numpy as np

from .base_data_store import BaseDataStore, DataStoreStats, Document, SearchResult
from .exceptions import CollectionNotFoundError


class SQLiteDataStore(BaseDataStore):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "data/rag_data.db")
        self.vector_enabled = config.get("vector_enabled", False)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    def _get_backend_type(self) -> str:
        return "sqlite"

    def _fts_table(self, collection_name: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)
        return f"fts_{safe}"

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            if self.vector_enabled:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vectors (
                        doc_id TEXT PRIMARY KEY,
                        embedding BLOB,
                        FOREIGN KEY (doc_id) REFERENCES documents(id)
                    )
                    """
                )

    def create_collection(
        self, collection_name: str, dimension: Optional[int] = None
    ) -> None:
        table = self._fts_table(collection_name)
        with sqlite3.connect(self.db_path) as conn:
            needs_recreate = False
            try:
                columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
                if columns and not any(col[1] == "doc_id" for col in columns):
                    needs_recreate = True
            except sqlite3.OperationalError:
                needs_recreate = False
            if needs_recreate:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {table}
                USING fts5(doc_id UNINDEXED, content)
                """
            )

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        doc_ids: List[str] = []
        table = self._fts_table(collection_name)
        with sqlite3.connect(self.db_path) as conn:
            for i, doc in enumerate(documents):
                doc_id = doc.metadata.get("doc_id", str(uuid.uuid4()))
                doc_ids.append(doc_id)
                conn.execute(
                    "INSERT OR REPLACE INTO documents (id, content, metadata) VALUES (?, ?, ?)",
                    (doc_id, doc.page_content, json.dumps(doc.metadata)),
                )
                conn.execute(
                    f"INSERT INTO {table} (doc_id, content) VALUES (?, ?)",
                    (doc_id, doc.page_content),
                )
                if self.vector_enabled and embeddings:
                    embedding_blob = np.array(embeddings[i], dtype=np.float32).tobytes()
                    conn.execute(
                        "INSERT OR REPLACE INTO vectors (doc_id, embedding) VALUES (?, ?)",
                        (doc_id, embedding_blob),
                    )
            conn.commit()
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
        table = self._fts_table(collection_name)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if search_method in ("keyword", "fulltext", "hybrid"):
                try:
                    cursor = conn.execute(
                        f"""
                        SELECT fts.doc_id, fts.content, d.metadata, rank
                        FROM {table} fts
                        LEFT JOIN documents d ON fts.doc_id = d.id
                        WHERE {table} MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, top_k),
                    )
                    for row in cursor:
                        score = self._normalize_score(row["rank"])
                        if score >= score_threshold:
                            results.append(
                                SearchResult(
                                    content=row["content"],
                                    score=score,
                                    doc_id=row["doc_id"],
                                    metadata=json.loads(row["metadata"] or "{}"),
                                    retrieval_method="fulltext",
                                )
                            )
                    if not results and score_threshold <= 0.5:
                        cursor = conn.execute(
                            f"""
                            SELECT fts.doc_id, fts.content, d.metadata
                            FROM {table} fts
                            LEFT JOIN documents d ON fts.doc_id = d.id
                            WHERE fts.content LIKE ?
                            LIMIT ?
                            """,
                            (f"%{query}%", top_k),
                        )
                        for row in cursor:
                            results.append(
                                SearchResult(
                                    content=row["content"],
                                    score=0.5,
                                    doc_id=row["doc_id"],
                                    metadata=json.loads(row["metadata"] or "{}"),
                                    retrieval_method="substring",
                                )
                            )
                except sqlite3.OperationalError as exc:
                    if "no such table" in str(exc):
                        raise CollectionNotFoundError(
                            f"Collection '{collection_name}' not found"
                        ) from exc
                    raise

            if (
                self.vector_enabled
                and search_method in ("semantic", "hybrid")
                and query_vector
            ):
                vector_results = self._vector_search(
                    conn, query_vector, top_k, score_threshold
                )
                results.extend(vector_results)

        return self._deduplicate_and_sort(results, top_k)

    def _vector_search(
        self,
        conn: sqlite3.Connection,
        query_vector: List[float],
        top_k: int,
        score_threshold: float,
    ) -> List[SearchResult]:
        query_vec = np.array(query_vector, dtype=np.float32)
        results: List[SearchResult] = []
        cursor = conn.execute("SELECT doc_id, embedding FROM vectors")
        for row in cursor:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            norm_product = np.linalg.norm(query_vec) * np.linalg.norm(embedding)
            similarity = (
                float(np.dot(query_vec, embedding) / norm_product)
                if norm_product > 0
                else 0.0
            )
            if similarity < score_threshold:
                continue
            doc_cursor = conn.execute(
                "SELECT content, metadata FROM documents WHERE id = ?",
                (row["doc_id"],),
            )
            doc = doc_cursor.fetchone()
            if doc:
                results.append(
                    SearchResult(
                        content=doc["content"],
                        score=similarity,
                        doc_id=row["doc_id"],
                        metadata=json.loads(doc["metadata"] or "{}"),
                        retrieval_method="vector",
                    )
                )
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _normalize_score(self, rank: float) -> float:
        return min(1.0, max(0.0, 1.0 / (1.0 + abs(rank))))

    def _deduplicate_and_sort(
        self, results: List[SearchResult], top_k: int
    ) -> List[SearchResult]:
        seen: set = set()
        unique_results: List[SearchResult] = []
        for r in results:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                unique_results.append(r)
        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:top_k]

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        table = self._fts_table(collection_name)
        with sqlite3.connect(self.db_path) as conn:
            for doc_id in doc_ids:
                conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.execute(f"DELETE FROM {table} WHERE doc_id = ?", (doc_id,))
                if self.vector_enabled:
                    conn.execute("DELETE FROM vectors WHERE doc_id = ?", (doc_id,))
            conn.commit()

    def delete_collection(self, collection_name: str) -> None:
        table = self._fts_table(collection_name)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()

    def get_stats(self, collection_name: str) -> DataStoreStats:
        with sqlite3.connect(self.db_path) as conn:
            total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            try:
                total_chunks = conn.execute(
                    f"SELECT COUNT(*) FROM {self._fts_table(collection_name)}"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                total_chunks = 0
            index_size = (
                os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            )
            return DataStoreStats(
                total_documents=total_docs,
                total_chunks=total_chunks,
                index_size_bytes=index_size,
                avg_query_latency_ms=0.0,
                backend_type="sqlite",
            )

    def health_check(self) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
