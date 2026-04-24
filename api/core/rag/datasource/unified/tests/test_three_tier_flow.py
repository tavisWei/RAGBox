import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from api.core.rag.datasource.unified.base_data_store import Document, SearchResult
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory
from api.core.rag.datasource.unified.sqlite_data_store import SQLiteDataStore
from api.core.rag.retrieval.multi_way_retriever import MultiWayRetriever
from api.core.rag.retrieval.reranker import Reranker
from api.services.resource_config_service import ResourceConfigService, ResourceLevel


@pytest.fixture(autouse=True)
def reset_service():
    ResourceConfigService.reset()
    yield
    ResourceConfigService.reset()


@pytest.fixture
def low_resource_config():
    config = ResourceConfigService.create_config(
        tenant_id="tenant_low",
        level=ResourceLevel.LOW,
        config_id="cfg_low",
    )
    ResourceConfigService.set_default_config("cfg_low")
    return config


@pytest.fixture
def medium_resource_config():
    config = ResourceConfigService.create_config(
        tenant_id="tenant_medium",
        level=ResourceLevel.MEDIUM,
        config_id="cfg_medium",
    )
    ResourceConfigService.set_default_config("cfg_medium")
    return config


@pytest.fixture
def high_resource_config():
    config = ResourceConfigService.create_config(
        tenant_id="tenant_high",
        level=ResourceLevel.HIGH,
        config_id="cfg_high",
    )
    ResourceConfigService.set_default_config("cfg_high")
    return config


@pytest.fixture
def sample_documents():
    return [
        Document(
            page_content="Python is a high-level programming language",
            metadata={"doc_id": "doc1", "category": "programming"},
        ),
        Document(
            page_content="Machine learning models require training data",
            metadata={"doc_id": "doc2", "category": "ai"},
        ),
        Document(
            page_content="PostgreSQL supports vector extensions",
            metadata={"doc_id": "doc3", "category": "database"},
        ),
        Document(
            page_content="Elasticsearch provides full-text search capabilities",
            metadata={"doc_id": "doc4", "category": "search"},
        ),
        Document(
            page_content="SQLite is a lightweight database engine",
            metadata={"doc_id": "doc5", "category": "database"},
        ),
    ]


@pytest.fixture
def sample_embeddings():
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [1.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


class TestLowResourceFlow:
    def test_full_lifecycle(self, low_resource_config, sample_documents):
        assert low_resource_config.level == ResourceLevel.LOW
        assert low_resource_config.data_store_type == "sqlite"

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create(
                "sqlite", {"db_path": db_path, "vector_enabled": False}
            )
            assert store.backend_type == "sqlite"

            store.create_collection("kb_low")

            doc_ids = store.add_documents("kb_low", sample_documents)
            assert len(doc_ids) == 5
            assert "doc1" in doc_ids

            results = store.search("kb_low", "Python", search_method="fulltext")
            assert len(results) >= 1
            assert results[0].doc_id == "doc1"
            assert results[0].retrieval_method == "fulltext"

            results = store.search("kb_low", "database", search_method="keyword")
            assert len(results) >= 1
            doc_ids_found = [r.doc_id for r in results]
            assert "doc3" in doc_ids_found or "doc5" in doc_ids_found

            results = store.search("kb_low", "search", search_method="hybrid")
            assert len(results) >= 1

            stats = store.get_stats("kb_low")
            assert stats.total_documents == 5
            assert stats.total_chunks == 5
            assert stats.backend_type == "sqlite"

            assert store.health_check() is True

            store.delete_documents("kb_low", ["doc1", "doc2"])
            results = store.search("kb_low", "Python", search_method="fulltext")
            assert len(results) == 0

            store.delete_collection("kb_low")

        finally:
            os.unlink(db_path)

    def test_with_multi_way_retriever(self, low_resource_config, sample_documents):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create(
                "sqlite", {"db_path": db_path, "vector_enabled": False}
            )
            store.create_collection("kb_low")
            store.add_documents("kb_low", sample_documents)

            retriever = MultiWayRetriever(data_store=store)
            results = retriever.retrieve(
                "kb_low", "programming language", methods=["fulltext"]
            )
            assert len(results) >= 1
            assert results[0].doc_id == "doc1"

        finally:
            os.unlink(db_path)


class TestMediumResourceFlow:
    def test_config_and_factory(self, medium_resource_config):
        assert medium_resource_config.level == ResourceLevel.MEDIUM
        assert medium_resource_config.data_store_type == "pgvector"
        assert medium_resource_config.config_json["vector_enabled"] is True
        assert medium_resource_config.config_json["rerank_enabled"] is True

        stores = DataStoreFactory.get_available_stores()
        assert "pgvector" in stores

    def test_mocked_pgvector_lifecycle(self, medium_resource_config, sample_documents):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            from api.core.rag.datasource.unified.pgvector_data_store import (
                PGVectorDataStore,
            )

            store = PGVectorDataStore(
                config={
                    "host": "localhost",
                    "port": 5432,
                    "database": "test_db",
                    "user": "test_user",
                    "password": "test_pass",
                }
            )

            with patch.object(store, "_get_connection", return_value=mock_conn):
                assert store.backend_type == "pgvector"
                store.create_collection("kb_medium", dimension=768)
                mock_cur.execute.assert_called()

                doc_ids = store.add_documents("kb_medium", sample_documents)
                assert len(doc_ids) == 5
                mock_conn.commit.assert_called()

                mock_cur.fetchone.return_value = (1,)
                assert store.health_check() is True

    def test_reranker_integration(self, medium_resource_config):
        def mock_rerank(query, results):
            return [(results[1], 0.99), (results[0], 0.5)]

        reranker = Reranker(rerank_fn=mock_rerank, model_name="bge-reranker", top_k=2)

        results = [
            SearchResult(
                content="a",
                score=0.9,
                doc_id="d1",
                metadata={},
                retrieval_method="vector",
            ),
            SearchResult(
                content="b",
                score=0.8,
                doc_id="d2",
                metadata={},
                retrieval_method="fulltext",
            ),
        ]

        reranked = reranker.rerank("query", results)
        assert len(reranked) == 2
        assert reranked[0].doc_id == "d2"
        assert reranked[0].metadata["reranker_model"] == "bge-reranker"
        assert reranked[0].retrieval_method == "reranked_fulltext"


class MockElasticsearchModule:
    class Elasticsearch:
        pass


sys.modules["elasticsearch"] = MockElasticsearchModule()


class TestHighResourceFlow:
    def test_config_and_factory(self, high_resource_config):
        assert high_resource_config.level == ResourceLevel.HIGH
        assert high_resource_config.data_store_type == "elasticsearch"
        assert (
            high_resource_config.config_json["embedding_model"]
            == "text-embedding-3-large"
        )
        assert high_resource_config.config_json["chunk_size"] == 1000

        stores = DataStoreFactory.get_available_stores()
        assert "elasticsearch" in stores

    def test_mocked_elasticsearch_lifecycle(
        self, high_resource_config, sample_documents
    ):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = False
        mock_es.indices.create.return_value = {"acknowledged": True}
        mock_es.bulk.return_value = {"errors": False}
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc1",
                        "_score": 0.95,
                        "_source": {
                            "content": "Python is a high-level programming language",
                            "metadata": {"category": "programming"},
                        },
                    }
                ]
            }
        }
        mock_es.cluster.health.return_value = {"status": "green"}
        mock_es.count.return_value = {"count": 5}
        mock_es.ping.return_value = True
        mock_es.indices.stats.return_value = {
            "indices": {
                "kb_high": {
                    "total": {
                        "docs": {"count": 5},
                        "store": {"size_in_bytes": 1024},
                    }
                }
            }
        }

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            from api.core.rag.datasource.unified.elasticsearch_data_store import (
                ElasticsearchDataStore,
            )

            store = ElasticsearchDataStore(
                config={
                    "hosts": ["http://localhost:9200"],
                    "username": "elastic",
                    "password": "changeme",
                }
            )

            assert store.backend_type == "elasticsearch"
            store.create_collection("kb_high", dimension=768)
            mock_es.indices.create.assert_called_once()

            doc_ids = store.add_documents("kb_high", sample_documents)
            assert len(doc_ids) == 5
            assert mock_es.index.call_count == 5

            results = store.search("kb_high", "programming", search_method="semantic")
            assert len(results) >= 1
            assert results[0].doc_id == "doc1"

            results = store.search("kb_high", "Python", search_method="fulltext")
            assert len(results) >= 1

            results = store.search(
                "kb_high", "Python", query_vector=[1.0] * 768, search_method="hybrid"
            )
            mock_es.search.assert_called()

            stats = store.get_stats("kb_high")
            assert stats.total_documents == 5
            assert stats.backend_type == "elasticsearch"

            assert store.health_check() is True

            store.delete_documents("kb_high", ["doc1"])
            mock_es.delete.assert_called_with(index="kb_high", id="doc1", ignore=[404])

            store.delete_collection("kb_high")
            mock_es.indices.delete.assert_called_once()

    def test_hybrid_search_with_rrf(self, high_resource_config):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = True
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc1",
                        "_score": 0.9,
                        "_source": {
                            "content": "Python programming",
                            "metadata": {},
                        },
                    },
                    {
                        "_id": "doc2",
                        "_score": 0.8,
                        "_source": {
                            "content": "Machine learning",
                            "metadata": {},
                        },
                    },
                ]
            }
        }

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            from api.core.rag.datasource.unified.elasticsearch_data_store import (
                ElasticsearchDataStore,
            )

            store = ElasticsearchDataStore(config={"hosts": ["http://localhost:9200"]})
            results = store.search(
                "kb_high",
                "Python ML",
                query_vector=[0.1] * 768,
                search_method="hybrid",
            )
            assert len(results) >= 1
            assert results[0].doc_id in ("doc1", "doc2")


class TestThreeTierComparison:
    def test_default_configs_differ(self):
        low = ResourceConfigService.get_default_config(ResourceLevel.LOW)
        medium = ResourceConfigService.get_default_config(ResourceLevel.MEDIUM)
        high = ResourceConfigService.get_default_config(ResourceLevel.HIGH)

        assert low["data_store_type"] == "sqlite"
        assert medium["data_store_type"] == "pgvector"
        assert high["data_store_type"] == "elasticsearch"

        assert low["vector_enabled"] is False
        assert medium["vector_enabled"] is True
        assert high["vector_enabled"] is True

        assert low["rerank_enabled"] is False
        assert medium["rerank_enabled"] is True
        assert high["rerank_enabled"] is True

        assert low["max_documents"] == 10000
        assert medium["max_documents"] == 1000000
        assert high["max_documents"] == 100000000

    def test_dataset_binding_flow(self):
        cfg_low = ResourceConfigService.create_config(
            tenant_id="t1", level=ResourceLevel.LOW, config_id="cfg_low"
        )
        cfg_medium = ResourceConfigService.create_config(
            tenant_id="t1", level=ResourceLevel.MEDIUM, config_id="cfg_medium"
        )
        cfg_high = ResourceConfigService.create_config(
            tenant_id="t1", level=ResourceLevel.HIGH, config_id="cfg_high"
        )

        ResourceConfigService.bind_dataset_to_config("ds_low", "cfg_low")
        ResourceConfigService.bind_dataset_to_config("ds_medium", "cfg_medium")
        ResourceConfigService.bind_dataset_to_config("ds_high", "cfg_high")

        assert (
            ResourceConfigService.get_config_for_dataset("ds_low").level
            == ResourceLevel.LOW
        )
        assert (
            ResourceConfigService.get_config_for_dataset("ds_medium").level
            == ResourceLevel.MEDIUM
        )
        assert (
            ResourceConfigService.get_config_for_dataset("ds_high").level
            == ResourceLevel.HIGH
        )

        ResourceConfigService.set_default_config("cfg_medium")
        assert (
            ResourceConfigService.get_config_for_dataset("unbound_ds").level
            == ResourceLevel.MEDIUM
        )

    def test_factory_creates_correct_backend_per_level(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store_low = DataStoreFactory.create("sqlite", {"db_path": db_path})
            assert store_low.backend_type == "sqlite"
            assert isinstance(store_low, SQLiteDataStore)

            stores = DataStoreFactory.get_available_stores()
            assert "pgvector" in stores
            assert "elasticsearch" in stores

        finally:
            os.unlink(db_path)

    def test_end_to_end_with_vector_enabled_sqlite(
        self, sample_documents, sample_embeddings
    ):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create(
                "sqlite", {"db_path": db_path, "vector_enabled": True}
            )
            store.create_collection("kb_vec", dimension=3)
            store.add_documents("kb_vec", sample_documents, sample_embeddings)

            results = store.search(
                "kb_vec",
                "database",
                query_vector=[0.0, 0.0, 1.0],
                search_method="semantic",
            )
            assert len(results) >= 1
            assert results[0].retrieval_method == "vector"

            results = store.search(
                "kb_vec",
                "Python",
                query_vector=[1.0, 0.0, 0.0],
                search_method="hybrid",
            )
            assert len(results) >= 1

        finally:
            os.unlink(db_path)

    def test_multi_way_retriever_with_reranker_across_levels(self, sample_documents):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create(
                "sqlite", {"db_path": db_path, "vector_enabled": True}
            )
            store.create_collection("kb_all")

            embeddings = [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
            store.add_documents("kb_all", sample_documents, embeddings)

            def mock_rerank(query, results):
                sorted_results = sorted(
                    results,
                    key=lambda r: 1.0 if r.doc_id == "doc4" else r.score,
                    reverse=True,
                )
                return [
                    (r, 0.9 if r.doc_id == "doc4" else r.score) for r in sorted_results
                ]

            reranker = Reranker(rerank_fn=mock_rerank, top_k=3)
            retriever = MultiWayRetriever(data_store=store, reranker=reranker)

            results = retriever.retrieve(
                "kb_all",
                "search",
                query_vector=[1.0, 1.0, 0.0],
                methods=["vector", "fulltext"],
                top_k=3,
            )

            assert len(results) <= 3
            assert results[0].doc_id == "doc4"
            assert results[0].score == 0.9
            assert "reranked_" in results[0].retrieval_method

        finally:
            os.unlink(db_path)

    def test_health_checks_across_backends(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create("sqlite", {"db_path": db_path})
            assert store.health_check() is True

            bad_path = os.path.join(tempfile.gettempdir(), "readonly", "test.db")
            bad_store = DataStoreFactory.create("sqlite", {"db_path": bad_path})
            assert hasattr(bad_store, "health_check")

        finally:
            os.unlink(db_path)

    def test_document_filtering_by_metadata(self, sample_documents):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create("sqlite", {"db_path": db_path})
            store.create_collection("kb_filter")
            store.add_documents("kb_filter", sample_documents)

            results = store.search("kb_filter", "database", search_method="fulltext")
            categories = [r.metadata.get("category") for r in results]
            assert "database" in categories

            for r in results:
                assert r.doc_id.startswith("doc")
                assert r.score > 0

        finally:
            os.unlink(db_path)

    def test_score_threshold_filtering(self, sample_documents):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create("sqlite", {"db_path": db_path})
            store.create_collection("kb_threshold")
            store.add_documents("kb_threshold", sample_documents)

            results = store.search(
                "kb_threshold",
                "completely unrelated query xyz",
                search_method="fulltext",
                score_threshold=0.99,
            )
            assert len(results) == 0

            results = store.search(
                "kb_threshold",
                "Python",
                search_method="fulltext",
                score_threshold=0.0,
            )
            assert len(results) >= 1

        finally:
            os.unlink(db_path)

    def test_config_listing_and_deletion(self):
        ResourceConfigService.create_config(
            tenant_id="t1", level=ResourceLevel.LOW, config_id="c1"
        )
        ResourceConfigService.create_config(
            tenant_id="t1", level=ResourceLevel.MEDIUM, config_id="c2"
        )
        ResourceConfigService.create_config(
            tenant_id="t2", level=ResourceLevel.HIGH, config_id="c3"
        )

        all_configs = ResourceConfigService.list_configs()
        assert len(all_configs) == 3

        t1_configs = ResourceConfigService.list_configs(tenant_id="t1")
        assert len(t1_configs) == 2

        ResourceConfigService.delete_config("c1")
        assert ResourceConfigService.get_config("c1") is None
        assert len(ResourceConfigService.list_configs()) == 2

    def test_unbind_dataset_clears_binding(self):
        cfg = ResourceConfigService.create_config(
            tenant_id="t1", level=ResourceLevel.MEDIUM, config_id="cfg1"
        )
        ResourceConfigService.bind_dataset_to_config("ds1", "cfg1")
        assert ResourceConfigService.get_config_for_dataset("ds1") == cfg

        ResourceConfigService.unbind_dataset("ds1")
        assert ResourceConfigService.get_config_for_dataset("ds1") is None

    def test_factory_env_var_fallback(self, monkeypatch):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            monkeypatch.setenv("DATA_STORE_TYPE", "sqlite")
            store = DataStoreFactory.create(config={"db_path": db_path})
            assert store.backend_type == "sqlite"
        finally:
            os.unlink(db_path)

    def test_error_handling_unknown_backend(self):
        from api.core.rag.datasource.unified.exceptions import BackendNotAvailableError

        with pytest.raises(BackendNotAvailableError):
            DataStoreFactory.create("nonexistent_backend")

    def test_collection_not_found_error(self):
        from api.core.rag.datasource.unified.exceptions import CollectionNotFoundError

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = DataStoreFactory.create("sqlite", {"db_path": db_path})
            with pytest.raises(CollectionNotFoundError):
                store.search("nonexistent_collection", "query")
        finally:
            os.unlink(db_path)
