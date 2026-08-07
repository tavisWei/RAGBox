"""Tests for the real index processor implementations and index_mode wiring."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.core.rag.datasource.unified.sqlite_data_store import SQLiteDataStore
from api.core.rag.index_processor.processor.paragraph_index_processor import (
    ParagraphIndexProcessor,
)
from api.core.rag.index_processor.processor.parent_child_index_processor import (
    ParentChildIndexProcessor,
    collapse_parent_child_docs,
    flatten_parent_child,
)
from api.core.rag.index_processor.processor.qa_index_processor import QAIndexProcessor
from api.core.rag.models.document import Document


@pytest.fixture
def store(tmp_path):
    return SQLiteDataStore(
        {"db_path": str(tmp_path / "rag.sqlite"), "vector_enabled": False}
    )


def test_paragraph_processor_load_and_retrieve_roundtrip(store) -> None:
    processor = ParagraphIndexProcessor()
    docs = processor.transform(
        [Document(page_content="机器学习 是 人工智能 的 重要 分支 。 深度学习 推动 了 它 的 发展 。")],
        chunk_size=20,
        chunk_overlap=4,
    )
    assert len(docs) >= 1

    processor.load("ds1", docs, data_store=store, embeddings=None)
    hits = processor.retrieve("机器学习", "ds1", top_k=3, data_store=store)
    assert hits
    assert any("机器学习" in hit.page_content for hit in hits)

    processor.clean("ds1", data_store=store)
    from api.core.rag.datasource.unified.exceptions import CollectionNotFoundError

    with pytest.raises(CollectionNotFoundError):
        processor.retrieve("机器学习", "ds1", top_k=3, data_store=store)


def test_parent_child_transform_flatten_and_collapse() -> None:
    processor = ParentChildIndexProcessor(
        parent_chunk_size=30, child_chunk_size=10, chunk_overlap=2
    )
    text = "第一段 内容 。 第二段 内容 。 第三段 内容 。 第四段 内容 。"
    parents = processor.transform([Document(page_content=text)])
    assert parents
    assert all(parent.children for parent in parents)

    flattened = flatten_parent_child(parents)
    assert len(flattened) >= len(parents)
    for child in flattened:
        assert child.metadata["parent_id"]
        assert child.metadata["parent_content"]
        assert child.metadata["index_mode"] == "parent_child"

    # Collapse: two children of the same parent become one parent passage.
    parent_id = flattened[0].metadata["parent_id"]
    siblings = [c for c in flattened if c.metadata["parent_id"] == parent_id]
    docs = [
        {"content": c.page_content, "metadata": c.metadata} for c in siblings
    ]
    collapsed = collapse_parent_child_docs(docs)
    assert len(collapsed) == 1
    assert collapsed[0]["content"] == flattened[0].metadata["parent_content"]


def test_parent_child_retrieve_returns_parent_passage(store) -> None:
    processor = ParentChildIndexProcessor(
        parent_chunk_size=20, child_chunk_size=10, chunk_overlap=0
    )
    text = "阿尔法 甲 。 贝塔 乙 。 伽马 丙 。 德尔塔 丁 。"
    parents = processor.transform([Document(page_content=text)])
    children = flatten_parent_child(parents)
    processor.load("ds2", children, data_store=store, embeddings=None)

    hits = processor.retrieve("贝塔", "ds2", top_k=5, data_store=store)
    assert hits
    # The hit is a child chunk; the returned passage is its parent.
    assert any("贝塔" in hit.page_content for hit in hits)


def test_qa_processor_regex_extraction() -> None:
    processor = QAIndexProcessor()
    text = "Q: 什么是向量数据库？\nA: 存储向量的数据库。\nQ: 什么是嵌入？\nA: 文本的数值表示。"
    docs = processor.transform([Document(page_content=text)])
    assert len(docs) == 2
    assert docs[0].metadata["question"] == "什么是向量数据库？"
    assert "Q: 什么是向量数据库？" in docs[0].page_content


def test_qa_processor_llm_generation() -> None:
    def fake_llm(prompt: str) -> str:
        assert "文档内容" in prompt
        return "Q: 生成的问题？\nA: 生成的答案。"

    processor = QAIndexProcessor(llm_generate=True, llm_function=fake_llm)
    docs = processor.transform([Document(page_content="没有任何问答格式的普通段落。")])
    assert len(docs) == 1
    assert docs[0].metadata["question"] == "生成的问题？"


def test_qa_processor_without_llm_falls_back_to_chunks() -> None:
    processor = QAIndexProcessor(llm_generate=True, llm_function=None)
    docs = processor.transform(
        [Document(page_content="普通 段落 没有 问答 格式 。")],
        chunk_size=10,
        chunk_overlap=0,
    )
    assert docs
    assert all("chunk_index" in (d.metadata or {}) for d in docs)


async def test_add_document_route_supports_parent_child_mode(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from api.api import knowledge_bases as kb_module
    from api.main import app

    captured = {}

    class FakeRAGService:
        def __init__(self, resource_level=None, config=None):
            pass

        async def add_documents(self, knowledge_base_id, documents):
            captured["chunks"] = documents

    monkeypatch.setattr(kb_module, "RAGService", FakeRAGService)

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post(
        "/api/v1/knowledge-bases",
        json={"name": f"pc-{uuid4().hex[:6]}"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    kb_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={
            "splitter_config": {
                "index_mode": "parent_child",
                "parent_chunk_size": 20,
                "chunk_size": 8,
                "chunk_overlap": 0,
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        json={"content": "甲 段 。 乙 段 。 丙 段 。 丁 段 。 戊 段 。"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    chunks = captured["chunks"]
    assert chunks
    assert all(chunk.metadata.get("parent_id") for chunk in chunks)
    assert all(chunk.metadata.get("parent_content") for chunk in chunks)
