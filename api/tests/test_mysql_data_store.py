"""Mock-based unit tests for the MySQL data store (fake pymysql)."""

import sys
import types
from typing import Any, Dict, List

import numpy as np
import pytest

from api.core.rag.datasource.unified.base_data_store import Document


class FakeCursor:
    def __init__(self, conn: "FakeConnection"):
        self.conn = conn
        self._rows: List[Any] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        table_rows = self.conn.tables.get(self.conn.current_table(sql), [])
        normalized = " ".join(sql.split()).upper()
        if normalized.startswith("SELECT COUNT(*)"):
            self._rows = [(len(table_rows),)]
        elif "MATCH(CONTENT)" in normalized:
            if self.conn.fail_match:
                raise RuntimeError("ngram parser missing")
            needle = params[0]
            self._rows = [
                (r["id"], r["content"], r["metadata"], 1.0)
                for r in table_rows
                if needle in r["content"]
            ]
        elif "LIKE" in normalized:
            needle = params[0].strip("%")
            self._rows = [
                (r["id"], r["content"], r["metadata"], None)
                for r in table_rows
                if needle in r["content"]
            ]
        elif "WHERE EMBEDDING IS NOT NULL" in normalized:
            self._rows = [
                (r["id"], r["content"], r["metadata"], r["embedding"])
                for r in table_rows
            ]
        elif "SELECT ID, CONTENT, METADATA FROM" in normalized:
            if " IN " in normalized:
                wanted = set(params)
                self._rows = [
                    (r["id"], r["content"], r["metadata"])
                    for r in table_rows
                    if r["id"] in wanted
                ]
            else:
                self._rows = [
                    (r["id"], r["content"], r["metadata"]) for r in table_rows
                ]
        elif normalized.startswith("REPLACE INTO"):
            doc_id, content, metadata, blob, _ = params
            table_rows[:] = [r for r in table_rows if r["id"] != doc_id]
            table_rows.append(
                {
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata,
                    "embedding": blob,
                }
            )
            self._rows = []
        elif normalized.startswith("DELETE FROM"):
            wanted = set(params)
            table_rows[:] = [r for r in table_rows if r["id"] not in wanted]
            self._rows = []
        elif normalized.startswith("DROP TABLE"):
            self.conn.tables.pop(self.conn.current_table(sql), None)
            self._rows = []
        elif normalized.startswith("CREATE TABLE"):
            self.conn.tables.setdefault(self.conn.current_table(sql), [])
            self._rows = []
        else:
            self._rows = []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.executed = []
        self.tables: Dict[str, list] = {}
        self.fail_match = False

    @staticmethod
    def current_table(sql: str) -> str:
        return sql.split("`")[1]

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def mysql_store(monkeypatch):
    fake = types.ModuleType("pymysql")
    shared = FakeConnection()

    def connect(**kwargs):
        conn = FakeConnection(**kwargs)
        conn.tables = shared.tables
        conn.executed = shared.executed
        conn.fail_match = shared.fail_match
        return conn

    fake.connect = connect
    monkeypatch.setitem(sys.modules, "pymysql", fake)

    from api.core.rag.datasource.unified.mysql_data_store import MySQLDataStore

    store = MySQLDataStore({"host": "fake", "user": "u", "password": "p"})
    return store, shared


def test_mysql_create_collection_ngram_fulltext(mysql_store) -> None:
    store, conn = mysql_store
    store.create_collection("kb1", dimension=4)
    create_sql = next(sql for sql, _ in conn.executed if "CREATE TABLE" in sql)
    assert "FULLTEXT" in create_sql
    assert "ngram" in create_sql


def test_mysql_add_and_semantic_search(mysql_store) -> None:
    store, conn = mysql_store
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [
            Document(page_content="向量 检索", metadata={"knowledge_base_id": "kb1"}),
            Document(page_content="无关 内容", metadata={"knowledge_base_id": "kb1"}),
        ],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    results = store.search(
        "kb1", query="向量", query_vector=[0.9, 0.1], search_method="semantic"
    )
    assert results[0].doc_id == ids[0]
    assert results[0].score > 0.99


def test_mysql_fulltext_match_and_like_fallback(mysql_store) -> None:
    store, conn = mysql_store
    store.create_collection("kb1", dimension=2)
    store.add_documents(
        "kb1",
        [Document(page_content="苹果 是 水果", metadata={})],
        [[1.0, 0.0]],
    )
    hits = store.search("kb1", query="苹果", search_method="fulltext")
    assert hits and hits[0].content == "苹果 是 水果"
    assert any("MATCH(CONTENT)" in sql.upper() for sql, _ in conn.executed)

    conn.fail_match = True
    hits = store.search("kb1", query="苹果", search_method="fulltext")
    assert hits and hits[0].score == 0.5
    assert any("LIKE" in sql.upper() for sql, _ in conn.executed)


def test_mysql_get_by_ids_and_delete(mysql_store) -> None:
    store, conn = mysql_store
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [Document(page_content="甲", metadata={}), Document(page_content="乙", metadata={})],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    fetched = store.get_documents_by_ids("kb1", [ids[1], ids[0]])
    assert [r.doc_id for r in fetched] == [ids[1], ids[0]]

    store.delete_documents("kb1", [ids[0]])
    assert store.get_stats("kb1").total_documents == 1
    store.delete_collection("kb1")
    assert "rag_kb1" not in conn.tables
