"""Tests for the jieba keyword retrieval leg."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.services import rag_service as rag_module
from api.services.document_processor import DocumentChunk
from api.services.rag_service import RAGService


class FakeEmbeddingService:
    def __init__(self, config=None):
        self.config = SimpleNamespace(provider="openai")
        self._provider = None

    def _create_provider(self, config):
        return None

    async def embed_single(self, text: str):
        return [0.1] * 8


class FakeLLMService:
    def __init__(self, **kwargs):
        pass

    async def chat(self, messages, config=None):
        return SimpleNamespace(content="答案")

    async def chat_stream(self, messages, config=None):
        yield "答案"


@pytest.fixture
def rag(monkeypatch) -> RAGService:
    monkeypatch.setattr(
        rag_module, "EmbeddingService", lambda config: FakeEmbeddingService(config)
    )
    monkeypatch.setattr(rag_module, "LLMService", lambda **kwargs: FakeLLMService())
    return RAGService(
        config={
            "llm_provider": "fake",
            "llm_model": "fake-model",
            "data_store_type": "sqlite",
        }
    )


async def test_keyword_leg_finds_doc_without_vector_match(rag: RAGService) -> None:
    pytest.importorskip("jieba")
    kb_id = f"kb-{uuid4().hex[:8]}"
    await rag.add_documents(
        kb_id,
        [
            DocumentChunk(
                content="量子纠缠是量子力学中的一种独特现象",
                chunk_index=0,
                start_char=0,
                end_char=18,
                metadata={},
            )
        ],
    )

    # Uniform fake embeddings make the vector leg useless; only the jieba
    # keyword leg can rank the document meaningfully here.
    rag.config["retrieval_config"] = {"methods": ["keyword"], "top_k": 5}
    docs = await rag._retrieve_docs("量子纠缠", kb_id, top_k=5, use_reranker=False)
    assert docs
    assert any("量子纠缠" in doc["content"] for doc in docs)
    assert docs[0]["metadata"].get("knowledge_base_id") == kb_id


async def test_keyword_table_rebuilds_from_store(rag: RAGService) -> None:
    pytest.importorskip("jieba")
    kb_id = f"kb-{uuid4().hex[:8]}"
    await rag.add_documents(
        kb_id,
        [
            DocumentChunk(
                content="光合作用把光能转化为化学能",
                chunk_index=0,
                start_char=0,
                end_char=12,
                metadata={},
            )
        ],
    )
    # Simulate a process restart: drop the in-memory table, then the keyword
    # leg must rebuild it from the data store.
    rag_module._keyword_tables.clear()

    rag.config["retrieval_config"] = {"methods": ["keyword"], "top_k": 5}
    docs = await rag._retrieve_docs("光合作用", kb_id, top_k=5, use_reranker=False)
    assert docs and "光合作用" in docs[0]["content"]


def test_sqlite_store_list_and_get_by_ids(tmp_path) -> None:
    from api.core.rag.datasource.unified.base_data_store import Document
    from api.core.rag.datasource.unified.sqlite_data_store import SQLiteDataStore

    store = SQLiteDataStore(
        {"db_path": str(tmp_path / "rag.sqlite"), "vector_enabled": False}
    )
    store.create_collection("kb1")
    ids = store.add_documents(
        "kb1",
        [
            Document(
                page_content="甲内容",
                metadata={"knowledge_base_id": "kb1"},
            ),
            Document(
                page_content="乙内容",
                metadata={"knowledge_base_id": "kb1"},
            ),
        ],
    )
    store.create_collection("kb2")
    store.add_documents(
        "kb2",
        [Document(page_content="其他库", metadata={"knowledge_base_id": "kb2"})],
    )

    listed = store.list_documents("kb1")
    assert {d["doc_id"] for d in listed} == set(ids)

    fetched = store.get_documents_by_ids("kb1", [ids[1], ids[0]])
    assert [r.doc_id for r in fetched] == [ids[1], ids[0]]
    assert fetched[0].content == "乙内容"
    # Cross-collection access is denied.
    assert store.get_documents_by_ids("kb2", ids) == []
