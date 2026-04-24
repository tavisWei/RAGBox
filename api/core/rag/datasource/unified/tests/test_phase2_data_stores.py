import uuid
from unittest.mock import MagicMock, patch

import pytest

from api.core.rag.datasource.unified.base_data_store import Document, SearchResult
from api.core.rag.datasource.unified.elasticsearch_data_store import ElasticsearchDataStore
from api.core.rag.datasource.unified.exceptions import (
    BackendNotAvailableError,
    CollectionNotFoundError,
    ConfigurationError,
)
from api.core.rag.datasource.unified.pgvector_data_store import PGVectorDataStore


class MockElasticsearchModule:
    class Elasticsearch:
        pass


import sys

sys.modules["elasticsearch"] = MockElasticsearchModule()


class TestPGVectorDataStore:
    def test_backend_type(self):
        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={"host": "localhost", "database": "test"})
            assert store.backend_type == "pgvector"

    def test_init_missing_psycopg2(self):
        with patch.dict("sys.modules", {"psycopg2": None, "psycopg2.extras": None}):
            with pytest.raises(ConfigurationError):
                PGVectorDataStore(config={})

    def test_create_collection(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={})

        with patch.object(store, "_get_connection", return_value=mock_conn):
            store.create_collection("test_col", dimension=768)

        calls = [call[0][0] for call in mock_cur.execute.call_args_list]
        assert any("CREATE TABLE IF NOT EXISTS test_col_docs" in str(c) for c in calls)
        assert any(
            "CREATE INDEX IF NOT EXISTS idx_test_col_fts" in str(c) for c in calls
        )
        assert any(
            "CREATE INDEX IF NOT EXISTS idx_test_col_vector" in str(c) for c in calls
        )
        mock_conn.commit.assert_called()

    def test_add_documents(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={})

        docs = [
            Document(page_content="doc 1", metadata={"doc_id": "d1"}),
            Document(page_content="doc 2", metadata={}),
        ]

        with patch.object(store, "_get_connection", return_value=mock_conn):
            doc_ids = store.add_documents("test_col", docs)

        assert len(doc_ids) == 2
        assert doc_ids[0] == "d1"
        assert isinstance(doc_ids[1], str)
        mock_conn.commit.assert_called()

    def test_delete_documents(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={})

        with patch.object(store, "_get_connection", return_value=mock_conn):
            store.delete_documents("test_col", ["d1", "d2"])

        mock_cur.executemany.assert_called_once()
        mock_conn.commit.assert_called()

    def test_delete_collection(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={})

        with patch.object(store, "_get_connection", return_value=mock_conn):
            store.delete_collection("test_col")

        mock_cur.execute.assert_called_once()
        assert "DROP TABLE IF EXISTS test_col_docs" in str(mock_cur.execute.call_args)

    def test_health_check_success(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={})

        with patch.object(store, "_get_connection", return_value=mock_conn):
            assert store.health_check() is True

    def test_health_check_failure(self):
        with patch(
            "api.core.rag.datasource.unified.pgvector_data_store.PGVectorDataStore._init_extensions"
        ):
            store = PGVectorDataStore(config={})

        with patch.object(
            store, "_get_connection", side_effect=Exception("connection failed")
        ):
            assert store.health_check() is False


class TestElasticsearchDataStore:
    def test_backend_type(self):
        with patch("elasticsearch.Elasticsearch"):
            store = ElasticsearchDataStore(config={"hosts": ["http://localhost:9200"]})
            assert store.backend_type == "elasticsearch"

    def test_init_missing_elasticsearch(self):
        with patch.dict("sys.modules", {"elasticsearch": None}):
            with pytest.raises(ConfigurationError):
                ElasticsearchDataStore(config={})

    def test_create_collection(self):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = False

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            store.create_collection("test_index", dimension=768)

        mock_es.indices.exists.assert_called_once_with(index="test_index")
        mock_es.indices.create.assert_called_once()
        call_args = mock_es.indices.create.call_args
        assert call_args[1]["index"] == "test_index"
        body = call_args[1]["body"]
        assert body["mappings"]["properties"]["embedding"]["dims"] == 768

    def test_add_documents(self):
        mock_es = MagicMock()

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            docs = [
                Document(page_content="hello", metadata={"doc_id": "d1"}),
                Document(page_content="world", metadata={}),
            ]
            embeddings = [[1.0, 0.0], [0.0, 1.0]]
            doc_ids = store.add_documents("test_index", docs, embeddings)

        assert len(doc_ids) == 2
        assert doc_ids[0] == "d1"
        assert mock_es.index.call_count == 2
        mock_es.indices.refresh.assert_called_once_with(index="test_index")

    def test_search_semantic(self):
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "d1",
                        "_score": 0.95,
                        "_source": {"content": "hello", "metadata": {"key": "val"}},
                    }
                ]
            }
        }

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            results = store.search(
                "test_index", "query", query_vector=[1.0, 0.0], search_method="semantic"
            )

        assert len(results) == 1
        assert results[0].doc_id == "d1"
        assert results[0].retrieval_method == "vector"
        mock_es.search.assert_called_once()

    def test_search_fulltext(self):
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "d2",
                        "_score": 1.2,
                        "_source": {"content": "world", "metadata": {}},
                    }
                ]
            }
        }

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            results = store.search("test_index", "world", search_method="fulltext")

        assert len(results) == 1
        assert results[0].doc_id == "d2"
        assert results[0].retrieval_method == "fulltext"

    def test_search_hybrid_rrf(self):
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "d1",
                        "_score": 0.8,
                        "_source": {"content": "hello world", "metadata": {}},
                    }
                ]
            }
        }

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            results = store.search(
                "test_index",
                "hello",
                query_vector=[1.0, 0.0],
                search_method="hybrid",
            )

        assert len(results) == 1
        assert results[0].retrieval_method == "hybrid"
        mock_es.search.assert_called_once()
        body = mock_es.search.call_args[1]["body"]
        assert "rank" in body
        assert body["rank"]["rrf"]["rank_constant"] == 60

    def test_delete_documents(self):
        mock_es = MagicMock()

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            store.delete_documents("test_index", ["d1", "d2"])

        assert mock_es.delete.call_count == 2

    def test_delete_collection(self):
        mock_es = MagicMock()

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            store.delete_collection("test_index")

        mock_es.indices.delete.assert_called_once_with(index="test_index", ignore=[404])

    def test_get_stats(self):
        mock_es = MagicMock()
        mock_es.indices.stats.return_value = {
            "indices": {
                "test_index": {
                    "total": {
                        "docs": {"count": 42},
                        "store": {"size_in_bytes": 1024},
                    }
                }
            }
        }

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            stats = store.get_stats("test_index")

        assert stats.total_documents == 42
        assert stats.index_size_bytes == 1024
        assert stats.backend_type == "elasticsearch"

    def test_health_check_success(self):
        mock_es = MagicMock()
        mock_es.ping.return_value = True

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            assert store.health_check() is True

    def test_health_check_failure(self):
        mock_es = MagicMock()
        mock_es.ping.side_effect = Exception("es down")

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            assert store.health_check() is False

    def test_search_collection_not_found(self):
        mock_es = MagicMock()
        mock_es.search.side_effect = Exception("index_not_found_exception")

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            with pytest.raises(CollectionNotFoundError):
                store.search("missing", "query")

    def test_search_with_filters(self):
        mock_es = MagicMock()
        mock_es.search.return_value = {"hits": {"hits": []}}

        with patch("elasticsearch.Elasticsearch", return_value=mock_es):
            store = ElasticsearchDataStore(config={})
            store.search("test_index", "query", filters={"tenant_id": "t1"})

        body = mock_es.search.call_args[1]["body"]
        assert "bool" in body["query"]
        assert "filter" in body["query"]["bool"]


class TestDataStoreFactoryRegistration:
    def test_factory_registers_pgvector(self):
        from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

        DataStoreFactory._register_builtin_backends()
        stores = DataStoreFactory.get_available_stores()
        assert "pgvector" in stores
        assert "elasticsearch" in stores

    def test_factory_creates_pgvector_mocked(self):
        from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

        with patch.object(
            DataStoreFactory, "_register_builtin_backends"
        ) as mock_register:
            mock_register.return_value = None
            DataStoreFactory._registry["pgvector"] = MagicMock()
            DataStoreFactory._registry["pgvector"].return_value = MagicMock()

            store = DataStoreFactory.create("pgvector", {"host": "localhost"})
            assert store is not None

    def test_factory_creates_elasticsearch_mocked(self):
        from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

        with patch.object(
            DataStoreFactory, "_register_builtin_backends"
        ) as mock_register:
            mock_register.return_value = None
            DataStoreFactory._registry["elasticsearch"] = MagicMock()
            DataStoreFactory._registry["elasticsearch"].return_value = MagicMock()

            store = DataStoreFactory.create(
                "elasticsearch", {"hosts": ["http://localhost:9200"]}
            )
            assert store is not None
