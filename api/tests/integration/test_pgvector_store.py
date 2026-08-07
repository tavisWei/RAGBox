"""pgvector data store integration tests against a real PostgreSQL container.

Requires a reachable pgvector instance (default: the local docker container at
localhost:5432, database rag_test). Run with:
    PGVECTOR_TEST_DSN=postgresql://aiwriter:aiwriter@localhost:5432/rag_test \
        pytest api/tests/integration/test_pgvector_store.py -m integration
"""

import os
import uuid

import pytest

from api.core.rag.datasource.unified.base_data_store import Document
from api.services.rag_service import _pgvector_config_from_env

pytestmark = pytest.mark.integration

TEST_DSN = os.getenv(
    "PGVECTOR_TEST_DSN", "postgresql://aiwriter:aiwriter@localhost:5432/rag_test"
)


def _dsn_available() -> bool:
    try:
        import psycopg2

        from urllib.parse import urlparse

        parsed = urlparse(TEST_DSN)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname=parsed.path.lstrip("/"),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


requires_pg = pytest.mark.skipif(not _dsn_available(), reason="pgvector test DSN unreachable")


def test_pgvector_config_from_dsn(monkeypatch) -> None:
    monkeypatch.setenv(
        "PGVECTOR_DSN", "postgresql+asyncpg://aiwriter:aiwriter@dbhost:5433/mydb"
    )
    config = _pgvector_config_from_env()
    assert config == {
        "host": "dbhost",
        "port": 5433,
        "user": "aiwriter",
        "password": "aiwriter",
        "database": "mydb",
    }


def test_pgvector_config_from_individual_vars(monkeypatch) -> None:
    monkeypatch.delenv("PGVECTOR_DSN", raising=False)
    monkeypatch.setenv("PGVECTOR_HOST", "pg.local")
    monkeypatch.setenv("PGVECTOR_DATABASE", "kb")
    monkeypatch.setenv("PGVECTOR_USER", "u")
    monkeypatch.setenv("PGVECTOR_PASSWORD", "p")
    config = _pgvector_config_from_env()
    assert config["host"] == "pg.local"
    assert config["database"] == "kb"


def test_pgvector_config_empty_without_env(monkeypatch) -> None:
    for var in ("PGVECTOR_DSN", "PGVECTOR_HOST", "PGVECTOR_DATABASE"):
        monkeypatch.delenv(var, raising=False)
    assert _pgvector_config_from_env() == {}


@requires_pg
def test_pgvector_store_end_to_end() -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    from api.core.rag.datasource.unified.pgvector_data_store import (
        PGVectorDataStore,
    )

    collection = f"it_{uuid.uuid4().hex[:12]}"
    store = PGVectorDataStore(
        {
            "host": "localhost",
            "port": 5432,
            "user": "aiwriter",
            "password": "aiwriter",
            "database": "rag_test",
        }
    )
    try:
        store.create_collection(collection, dimension=4)

        # HNSW index must exist when the dimension is explicit.
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="aiwriter",
            password="aiwriter",
            dbname="rag_test",
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s",
                    (f"{collection}_docs",),
                )
                indexes = cur.fetchall()
        finally:
            conn.close()
        assert any("hnsw" in indexdef.lower() for _, indexdef in indexes), indexes

        docs = [
            Document(
                page_content="向量数据库用于存储和检索嵌入向量",
                metadata={"doc_id": "d1", "knowledge_base_id": collection},
            ),
            Document(
                page_content="今天天气晴朗适合户外运动",
                metadata={"doc_id": "d2", "knowledge_base_id": collection},
            ),
        ]
        embeddings = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
        ids = store.add_documents(collection, docs, embeddings)
        assert len(ids) == 2

        semantic = store.search(
            collection,
            query="嵌入",
            query_vector=[0.9, 0.1, 0.0, 0.0],
            top_k=1,
            search_method="semantic",
        )
        assert semantic and semantic[0].metadata["doc_id"] == "d1"
        assert semantic[0].score > 0.9

        fulltext = store.search(
            collection, query="天气", top_k=5, search_method="fulltext"
        )
        assert fulltext and fulltext[0].metadata["doc_id"] == "d2"

        hybrid = store.search(
            collection,
            query="向量",
            query_vector=[1.0, 0.0, 0.0, 0.0],
            top_k=5,
            search_method="hybrid",
        )
        assert {r.metadata["doc_id"] for r in hybrid} == {"d1", "d2"}
    finally:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="aiwriter",
            password="aiwriter",
            dbname="rag_test",
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{collection}_docs"')
        conn.close()
