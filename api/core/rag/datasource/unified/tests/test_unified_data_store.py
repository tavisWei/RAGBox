import os
import tempfile
import uuid

import pytest

from api.core.rag.datasource.unified.base_data_store import BaseDataStore, Document
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory
from api.core.rag.datasource.unified.exceptions import (
    BackendNotAvailableError,
    CollectionNotFoundError,
)
from api.core.rag.datasource.unified.sqlite_data_store import SQLiteDataStore


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def sqlite_store(temp_db_path):
    return SQLiteDataStore(config={"db_path": temp_db_path})


class TestSQLiteDataStore:
    def test_backend_type(self, sqlite_store):
        assert sqlite_store.backend_type == "sqlite"

    def test_health_check(self, sqlite_store):
        assert sqlite_store.health_check() is True

    def test_create_collection(self, sqlite_store):
        sqlite_store.create_collection("test_collection")
        stats = sqlite_store.get_stats("test_collection")
        assert stats.backend_type == "sqlite"

    def test_add_and_search_documents(self, sqlite_store):
        sqlite_store.create_collection("docs")
        docs = [
            Document(page_content="Hello world", metadata={"doc_id": "doc1"}),
            Document(page_content="Python programming", metadata={"doc_id": "doc2"}),
        ]
        doc_ids = sqlite_store.add_documents("docs", docs)
        assert len(doc_ids) == 2
        assert "doc1" in doc_ids

        results = sqlite_store.search("docs", "hello", search_method="fulltext")
        assert len(results) >= 1
        assert results[0].doc_id == "doc1"
        assert results[0].retrieval_method == "fulltext"

    def test_search_with_score_threshold(self, sqlite_store):
        sqlite_store.create_collection("docs")
        docs = [
            Document(page_content="exact match content", metadata={"doc_id": "doc1"})
        ]
        sqlite_store.add_documents("docs", docs)
        results = sqlite_store.search("docs", "exact match", score_threshold=0.9999999)
        assert len(results) == 0

    def test_delete_documents(self, sqlite_store):
        sqlite_store.create_collection("docs")
        docs = [Document(page_content="to be deleted", metadata={"doc_id": "del1"})]
        sqlite_store.add_documents("docs", docs)
        sqlite_store.delete_documents("docs", ["del1"])
        results = sqlite_store.search("docs", "deleted", search_method="fulltext")
        assert len(results) == 0

    def test_delete_collection(self, sqlite_store):
        sqlite_store.create_collection("temp_col")
        sqlite_store.delete_collection("temp_col")
        with pytest.raises(CollectionNotFoundError):
            sqlite_store.search("temp_col", "test")

    def test_get_stats(self, sqlite_store):
        sqlite_store.create_collection("stats_col")
        docs = [Document(page_content="stat test", metadata={})]
        sqlite_store.add_documents("stats_col", docs)
        stats = sqlite_store.get_stats("stats_col")
        assert stats.total_documents >= 1
        assert stats.total_chunks >= 1
        assert stats.backend_type == "sqlite"
        assert stats.index_size_bytes >= 0

    def test_vector_search(self, temp_db_path):
        store = SQLiteDataStore(
            config={"db_path": temp_db_path, "vector_enabled": True}
        )
        store.create_collection("vec_docs")
        docs = [
            Document(page_content="vector doc 1", metadata={"doc_id": "v1"}),
            Document(page_content="vector doc 2", metadata={"doc_id": "v2"}),
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
        store.add_documents("vec_docs", docs, embeddings)
        results = store.search(
            "vec_docs", "query", query_vector=[1.0, 0.0, 0.0], search_method="semantic"
        )
        assert len(results) >= 1
        assert results[0].doc_id == "v1"
        assert results[0].retrieval_method == "vector"

    def test_hybrid_search(self, temp_db_path):
        store = SQLiteDataStore(
            config={"db_path": temp_db_path, "vector_enabled": True}
        )
        store.create_collection("hybrid_docs")
        docs = [
            Document(page_content="hybrid search test", metadata={"doc_id": "h1"}),
            Document(page_content="another document", metadata={"doc_id": "h2"}),
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
        store.add_documents("hybrid_docs", docs, embeddings)
        results = store.search(
            "hybrid_docs",
            "hybrid search",
            query_vector=[1.0, 0.0, 0.0],
            search_method="hybrid",
        )
        assert len(results) >= 1

    def test_collection_not_found(self, sqlite_store):
        with pytest.raises(CollectionNotFoundError):
            sqlite_store.search("nonexistent", "query")


class TestDataStoreFactory:
    def test_create_sqlite(self, temp_db_path):
        store = DataStoreFactory.create("sqlite", {"db_path": temp_db_path})
        assert isinstance(store, SQLiteDataStore)
        assert store.backend_type == "sqlite"

    def test_create_unknown_backend(self):
        with pytest.raises(BackendNotAvailableError):
            DataStoreFactory.create("unknown")

    def test_get_available_stores(self):
        stores = DataStoreFactory.get_available_stores()
        assert "sqlite" in stores

    def test_register_backend(self):
        class FakeStore(BaseDataStore):
            def _get_backend_type(self):
                return "fake"

            def create_collection(self, collection_name, dimension=None):
                pass

            def add_documents(self, collection_name, documents, embeddings=None):
                return []

            def search(
                self,
                collection_name,
                query,
                query_vector=None,
                top_k=10,
                score_threshold=0.0,
                filters=None,
                search_method="hybrid",
            ):
                return []

            def delete_documents(self, collection_name, doc_ids):
                pass

            def delete_collection(self, collection_name):
                pass

            def get_stats(self, collection_name):
                from api.core.rag.datasource.unified.base_data_store import (
                    DataStoreStats,
                )

                return DataStoreStats(0, 0, 0, 0.0, "fake")

            def health_check(self):
                return True

        DataStoreFactory.register("fake", FakeStore)
        assert "fake" in DataStoreFactory.get_available_stores()
        store = DataStoreFactory.create("fake", {})
        assert isinstance(store, FakeStore)

    def test_env_var_fallback(self, monkeypatch, temp_db_path):
        monkeypatch.setenv("DATA_STORE_TYPE", "sqlite")
        store = DataStoreFactory.create(config={"db_path": temp_db_path})
        assert store.backend_type == "sqlite"


class TestDocumentModel:
    def test_document_creation(self):
        doc = Document(page_content="test", metadata={"key": "value"})
        assert doc.page_content == "test"
        assert doc.metadata == {"key": "value"}

    def test_document_defaults(self):
        doc = Document(page_content="test")
        assert doc.metadata == {}
