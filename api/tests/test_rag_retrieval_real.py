"""Tests for the real (non-stub) retrieval wiring in RAGService:

- query expansion / LLM rerank receive a working llm_fn bridge
- use_reranker=False actually disables reranking
- query_stream streams real LLM tokens instead of replaying split words
"""

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
        self.chat_prompts = []
        self.stream_used = False

    async def chat(self, messages, config=None):
        self.chat_prompts.append(messages[-1].content)
        return SimpleNamespace(content="2. 备用问题一\n3. 备用问题二")

    async def chat_stream(self, messages, config=None):
        self.stream_used = True
        for token in ["你好", "，", "世界"]:
            yield token


@pytest.fixture
def rag(monkeypatch) -> RAGService:
    monkeypatch.setattr(
        rag_module, "EmbeddingService", lambda config: FakeEmbeddingService(config)
    )
    created = {}

    def fake_llm_factory(**kwargs):
        created["llm"] = FakeLLMService(**kwargs)
        return created["llm"]

    monkeypatch.setattr(rag_module, "LLMService", fake_llm_factory)
    service = RAGService(
        config={
            "llm_provider": "fake",
            "llm_model": "fake-model",
            "data_store_type": "sqlite",
        }
    )
    service._test_llm = created["llm"]
    return service


async def test_query_expansion_receives_real_llm(rag: RAGService) -> None:
    kb_id = f"kb-{uuid4().hex[:8]}"
    await rag.add_documents(
        kb_id,
        [
            DocumentChunk(
                content="向量数据库用于存储嵌入向量并支持相似度检索",
                chunk_index=0,
                start_char=0,
                end_char=20,
                metadata={},
            )
        ],
    )
    rag.config["retrieval_config"] = {
        "methods": ["hybrid"],
        "top_k": 5,
        "query_expansion": "multi_query",
        "expansion_count": 2,
    }

    response = await rag.query("什么是向量数据库", kb_id)

    # The expansion prompt (containing the original query) must have reached
    # the LLM through the sync bridge — previously llm_fn returned "".
    assert any("什么是向量数据库" in prompt for prompt in rag._test_llm.chat_prompts)
    assert response.answer  # demo answer path completed
    assert response.sources


async def test_use_reranker_false_disables_rerank(rag: RAGService, monkeypatch) -> None:
    captured = {}

    real_retriever = rag_module.MultiWayRetriever

    def spy_retriever(data_store, config, **kwargs):
        captured["rerank_mode"] = config.rerank_mode
        return real_retriever(data_store, config, **kwargs)

    monkeypatch.setattr(rag_module, "MultiWayRetriever", spy_retriever)
    await rag.query("anything", f"kb-{uuid4().hex[:8]}", use_reranker=False)

    from api.core.rag.retrieval.retrieval_config import RerankMode

    assert captured["rerank_mode"] == RerankMode.NONE


async def test_query_stream_uses_real_token_stream(rag: RAGService) -> None:
    chunks = [
        chunk
        async for chunk in rag.query_stream("你好", f"kb-{uuid4().hex[:8]}")
    ]
    assert rag._test_llm.stream_used is True
    assert "".join(chunks) == "你好，世界"


def test_llm_reranker_empty_response_keeps_original_order() -> None:
    from api.core.rag.datasource.unified.base_data_store import SearchResult
    from api.core.rag.retrieval.llm_reranker import LLMListwiseReranker

    results = [
        SearchResult(
            content=f"doc {i}",
            score=1.0 - i * 0.1,
            doc_id=str(i),
            metadata={},
            retrieval_method="semantic",
        )
        for i in range(3)
    ]
    reranker = LLMListwiseReranker(llm_function=lambda prompt: "")
    reranked = reranker.rerank("query", results)
    # Empty/unparseable LLM output must not swallow the batch.
    assert [r.doc_id for r in reranked] == ["0", "1", "2"]
