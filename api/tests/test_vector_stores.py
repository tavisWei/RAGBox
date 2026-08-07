"""Mock-based unit tests for the Qdrant / Milvus / Elasticsearch data stores.

No live servers required: HTTP/SDK layers are faked, so these tests pin the
request construction and result mapping of each backend.
"""

import sys
import types
from typing import Any, Dict

import pytest

from api.core.rag.datasource.unified.base_data_store import Document


# ---------------------------------------------------------------------------
# Qdrant (fake httpx.Client)
# ---------------------------------------------------------------------------


class FakeHttpResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class FakeHttpxClient:
    """Minimal Qdrant REST fake recording every request."""

    def __init__(self, base_url=None, headers=None, timeout=None):
        self.base_url = base_url
        self.headers = headers
        self.requests = []
        self.collections: Dict[str, Dict[str, Any]] = {}

    def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        if path == "/collections":
            return FakeHttpResponse(200, {"result": {"collections": []}})
        if method == "GET" and path.startswith("/collections/"):
            name = path.split("/")[2]
            if name not in self.collections:
                return FakeHttpResponse(404, text="not found")
            return FakeHttpResponse(
                200, {"result": {"points_count": len(self.collections[name]["points"])}}
            )
        if method == "PUT" and path.endswith("/index"):
            return FakeHttpResponse(200, {"result": True})
        if method == "PUT" and path.startswith("/collections/"):
            name = path.split("/")[2]
            if "/points" in path:
                self.collections[name]["points"].extend(kwargs["json"]["points"])
                return FakeHttpResponse(200, {"result": True})
            self.collections[name] = {"points": [], "config": kwargs["json"]}
            return FakeHttpResponse(200, {"result": True})
        if method == "POST" and path.endswith("/points/search"):
            name = path.split("/")[2]
            vector = kwargs["json"]["vector"]
            hits = [
                {
                    "id": p["id"],
                    "score": 1.0 - abs(p["vector"][0] - vector[0]),
                    "payload": p["payload"],
                }
                for p in self.collections[name]["points"]
            ]
            return FakeHttpResponse(200, {"result": hits})
        if method == "POST" and path.endswith("/points/scroll"):
            name = path.split("/")[2]
            points = self.collections[name]["points"]
            match = (kwargs["json"].get("filter") or {}).get("must", [])
            if match:
                needle = match[0]["match"]["text"]
                points = [p for p in points if needle in p["payload"]["content"]]
            return FakeHttpResponse(
                200, {"result": {"points": points, "next_page_offset": None}}
            )
        if method == "POST" and path.endswith("/points/delete"):
            name = path.split("/")[2]
            doomed = set(kwargs["json"]["points"])
            self.collections[name]["points"] = [
                p for p in self.collections[name]["points"] if p["id"] not in doomed
            ]
            return FakeHttpResponse(200, {"result": True})
        if method == "POST" and path.endswith("/points"):
            name = path.split("/")[2]
            wanted = set(kwargs["json"]["ids"])
            points = [
                p for p in self.collections[name]["points"] if p["id"] in wanted
            ]
            return FakeHttpResponse(200, {"result": points})
        if method == "DELETE":
            name = path.split("/")[2]
            if name not in self.collections:
                return FakeHttpResponse(404, text="not found")
            del self.collections[name]
            return FakeHttpResponse(200, {"result": True})
        raise AssertionError(f"unhandled fake request: {method} {path}")


@pytest.fixture
def qdrant(monkeypatch):
    from api.core.rag.datasource.unified import qdrant_data_store

    created = {}

    def fake_client(**kwargs):
        client = FakeHttpxClient(**kwargs)
        created["client"] = client
        return client

    monkeypatch.setattr(qdrant_data_store.httpx, "Client", fake_client)
    store = qdrant_data_store.QdrantDataStore({"url": "http://fake:6333"})
    return store, created["client"]


def test_qdrant_create_collection_with_cosine(qdrant) -> None:
    store, client = qdrant
    store.create_collection("kb1", dimension=8)
    config = client.collections["kb1"]["config"]
    assert config["vectors"]["size"] == 8
    assert config["vectors"]["distance"] == "Cosine"


def test_qdrant_add_and_semantic_search(qdrant) -> None:
    store, client = qdrant
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [Document(page_content="向量检索", metadata={"knowledge_base_id": "kb1"})],
        [[1.0, 0.0]],
    )
    assert len(ids) == 1
    results = store.search(
        "kb1", query="向量", query_vector=[0.9, 0.1], search_method="semantic"
    )
    assert results and results[0].content == "向量检索"
    assert results[0].retrieval_method == "semantic"


def test_qdrant_fulltext_and_get_by_ids(qdrant) -> None:
    store, client = qdrant
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [
            Document(page_content="苹果是水果", metadata={}),
            Document(page_content="汽车是交通工具", metadata={}),
        ],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    fulltext = store.search("kb1", query="苹果", search_method="fulltext")
    assert [r.content for r in fulltext] == ["苹果是水果"]

    fetched = store.get_documents_by_ids("kb1", [ids[1], ids[0]])
    assert [r.doc_id for r in fetched] == [ids[1], ids[0]]


def test_qdrant_delete_and_stats(qdrant) -> None:
    store, client = qdrant
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [Document(page_content="甲", metadata={}), Document(page_content="乙", metadata={})],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    store.delete_documents("kb1", [ids[0]])
    assert store.get_stats("kb1").total_documents == 1
    store.delete_collection("kb1")
    assert "kb1" not in client.collections


# ---------------------------------------------------------------------------
# Milvus (fake pymilvus module)
# ---------------------------------------------------------------------------


@pytest.fixture
def milvus(monkeypatch):
    calls: Dict[str, Any] = {"collections": {}}

    fake = types.ModuleType("pymilvus")

    class DataType:
        VARCHAR = "varchar"
        JSON = "json"
        FLOAT_VECTOR = "float_vector"

    class FieldSchema:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class CollectionSchema:
        def __init__(self, fields):
            self.fields = fields

    class FakeCollection:
        def __init__(self, name, schema=None):
            self.name = name
            self.schema = schema
            self.index_params = None
            calls["collections"].setdefault(name, {"rows": []})

        def create_index(self, field_name, index_params):
            self.index_params = (field_name, index_params)
            calls["collections"][self.name]["index"] = index_params

        def insert(self, rows):
            ids, contents, metadatas, vectors = rows
            calls["collections"][self.name]["rows"].extend(
                [
                    {"id": i, "content": c, "metadata": m, "embedding": v}
                    for i, c, m, v in zip(ids, contents, metadatas, vectors)
                ]
            )

        def flush(self):
            pass

        def load(self):
            pass

        def release(self):
            pass

        def search(self, data, anns_field, param, limit, output_fields):
            calls["search_param"] = param
            rows = calls["collections"][self.name]["rows"]
            hit = types.SimpleNamespace(
                score=0.99,
                id=rows[0]["id"],
                entity={
                    "content": rows[0]["content"],
                    "metadata": rows[0]["metadata"],
                },
            )
            return [[hit]]

        def query(self, expr, output_fields, limit):
            rows = calls["collections"][self.name]["rows"]
            if "like" in expr:
                needle = expr.split('"')[1].strip("%")
                rows = [r for r in rows if needle in r["content"]]
            if " in " in expr:
                wanted = {
                    part.strip().strip('"')
                    for part in expr.split("[")[1].rstrip("]").split(",")
                }
                rows = [r for r in rows if r["id"] in wanted]
            return rows[:limit]

        def delete(self, expr):
            wanted = {
                part.strip().strip('"')
                for part in expr.split("[")[1].rstrip("]").split(",")
            }
            rows = calls["collections"][self.name]["rows"]
            calls["collections"][self.name]["rows"] = [
                r for r in rows if r["id"] not in wanted
            ]

        @property
        def num_entities(self):
            return len(calls["collections"][self.name]["rows"])

    fake.DataType = DataType
    fake.FieldSchema = FieldSchema
    fake.CollectionSchema = CollectionSchema
    fake.Collection = FakeCollection
    fake.connections = types.SimpleNamespace(
        connect=lambda **kwargs: calls.setdefault("connect", kwargs),
        has_connection=lambda alias: True,
    )
    fake.utility = types.SimpleNamespace(
        has_collection=lambda name: name in calls["collections"],
        drop_collection=lambda name: calls["collections"].pop(name, None),
    )
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    from api.core.rag.datasource.unified.milvus_data_store import MilvusDataStore

    return MilvusDataStore({"host": "fake", "port": 19530}), calls


def test_milvus_create_collection_hnsw_cosine(milvus) -> None:
    store, calls = milvus
    store.create_collection("kb1", dimension=8)
    index = calls["collections"]["kb1"]["index"]
    assert index["index_type"] == "HNSW"
    assert index["metric_type"] == "COSINE"


def test_milvus_add_search_and_delete(milvus) -> None:
    store, calls = milvus
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [Document(page_content="量子计算 简介", metadata={"knowledge_base_id": "kb1"})],
        [[0.1, 0.9]],
    )
    assert len(ids) == 1

    semantic = store.search(
        "kb1", query="量子", query_vector=[0.1, 0.9], search_method="semantic"
    )
    assert semantic and semantic[0].content == "量子计算 简介"
    assert calls["search_param"]["metric_type"] == "COSINE"

    fulltext = store.search("kb1", query="量子", search_method="fulltext")
    assert [r.doc_id for r in fulltext] == ids

    fetched = store.get_documents_by_ids("kb1", ids)
    assert fetched[0].content == "量子计算 简介"

    store.delete_documents("kb1", ids)
    assert store.get_stats("kb1").total_documents == 0


# ---------------------------------------------------------------------------
# Elasticsearch (fake elasticsearch module)
# ---------------------------------------------------------------------------


@pytest.fixture
def es_store(monkeypatch):
    calls: Dict[str, Any] = {"indexes": {}}

    class FakeIndices:
        def exists(self, index):
            return index in calls["indexes"]

        def create(self, index, body):
            calls["indexes"][index] = {"mapping": body, "docs": {}}

        def refresh(self, index):
            pass

    class FakeElasticsearch:
        def __init__(self, **kwargs):
            calls["conn_kwargs"] = kwargs
            self.indices = FakeIndices()

        def index(self, index, id, body):
            calls["indexes"][index]["docs"][id] = body

        def search(self, index, body):
            calls["search_body"] = body
            docs = calls["indexes"][index]["docs"]
            hits = [
                {
                    "_id": doc_id,
                    "_score": 1.0,
                    "_source": doc,
                }
                for doc_id, doc in docs.items()
            ]
            return {"hits": {"hits": hits}}

        def ping(self):
            return True

    fake = types.ModuleType("elasticsearch")
    fake.Elasticsearch = FakeElasticsearch
    monkeypatch.setitem(sys.modules, "elasticsearch", fake)

    from api.core.rag.datasource.unified.elasticsearch_data_store import (
        ElasticsearchDataStore,
    )

    store = ElasticsearchDataStore(
        {"hosts": ["http://fake:9200"], "username": "elastic", "password": "secret"}
    )
    return store, calls


def test_es_connects_with_basic_auth_and_creates_dense_vector(es_store) -> None:
    store, calls = es_store
    assert calls["conn_kwargs"]["basic_auth"] == ("elastic", "secret")

    store.create_collection("kb1", dimension=8)
    mapping = calls["indexes"]["kb1"]["mapping"]["mappings"]["properties"]
    assert mapping["embedding"]["type"] == "dense_vector"
    assert mapping["embedding"]["dims"] == 8
    assert mapping["embedding"]["similarity"] == "cosine"


def test_es_add_and_search(es_store) -> None:
    store, calls = es_store
    store.create_collection("kb1", dimension=2)
    ids = store.add_documents(
        "kb1",
        [Document(page_content="混合检索 介绍", metadata={"knowledge_base_id": "kb1"})],
        [[0.5, 0.5]],
    )

    results = store.search("kb1", query="混合", search_method="fulltext")
    assert results and results[0].doc_id == ids[0]
    assert results[0].metadata["knowledge_base_id"] == "kb1"
    assert "match" in calls["search_body"]["query"]

    knn_results = store.search(
        "kb1", query="混合", query_vector=[0.5, 0.5], search_method="semantic"
    )
    assert knn_results
    assert calls["search_body"]["knn"]["field"] == "embedding"
