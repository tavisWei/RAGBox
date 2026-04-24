import pytest

from api.core.rag.datasource.unified.base_data_store import SearchResult
from api.core.rag.retrieval.fusion_strategies import (
    reciprocal_rank_fusion,
    weighted_score_fusion,
)
from api.core.rag.retrieval.multi_way_retriever import MultiWayRetriever
from api.core.rag.retrieval.reranker import Reranker


class TestFusionStrategies:
    def test_reciprocal_rank_fusion_basic(self):
        list1 = [
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
                retrieval_method="vector",
            ),
        ]
        list2 = [
            SearchResult(
                content="b",
                score=0.85,
                doc_id="d2",
                metadata={},
                retrieval_method="fulltext",
            ),
            SearchResult(
                content="c",
                score=0.7,
                doc_id="d3",
                metadata={},
                retrieval_method="fulltext",
            ),
        ]

        fused = reciprocal_rank_fusion([list1, list2])

        assert len(fused) == 3
        doc_ids = [r.doc_id for r in fused]
        assert "d2" in doc_ids
        assert fused[0].retrieval_method == "fusion_rrf"
        assert fused[0].score > 0

    def test_reciprocal_rank_fusion_single_list(self):
        list1 = [
            SearchResult(
                content="a",
                score=0.9,
                doc_id="d1",
                metadata={},
                retrieval_method="vector",
            ),
        ]
        fused = reciprocal_rank_fusion([list1])
        assert len(fused) == 1
        assert fused[0].doc_id == "d1"

    def test_reciprocal_rank_fusion_empty(self):
        fused = reciprocal_rank_fusion([])
        assert fused == []

    def test_weighted_score_fusion_basic(self):
        list1 = [
            SearchResult(
                content="a",
                score=1.0,
                doc_id="d1",
                metadata={},
                retrieval_method="vector",
            ),
            SearchResult(
                content="b",
                score=0.5,
                doc_id="d2",
                metadata={},
                retrieval_method="vector",
            ),
        ]
        list2 = [
            SearchResult(
                content="b",
                score=0.8,
                doc_id="d2",
                metadata={},
                retrieval_method="fulltext",
            ),
            SearchResult(
                content="c",
                score=0.2,
                doc_id="d3",
                metadata={},
                retrieval_method="fulltext",
            ),
        ]

        fused = weighted_score_fusion([list1, list2], weights=[0.6, 0.4])

        assert len(fused) == 3
        assert fused[0].retrieval_method == "fusion_weighted"
        assert all(r.score >= 0 for r in fused)

    def test_weighted_score_fusion_mismatched_lengths(self):
        with pytest.raises(ValueError):
            weighted_score_fusion([[], []], weights=[0.5])

    def test_weighted_score_fusion_empty_lists(self):
        fused = weighted_score_fusion([[], []], weights=[0.5, 0.5])
        assert fused == []


class TestReranker:
    def test_noop_reranker(self):
        reranker = Reranker()
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
                retrieval_method="vector",
            ),
        ]
        reranked = reranker.rerank("query", results)
        assert len(reranked) == 2
        assert reranked[0].doc_id == "d1"

    def test_reranker_with_callback(self):
        def mock_rerank(query, results):
            return [(results[1], 0.99), (results[0], 0.5)]

        reranker = Reranker(rerank_fn=mock_rerank, model_name="test_model")
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
                retrieval_method="vector",
            ),
        ]
        reranked = reranker.rerank("query", results)
        assert len(reranked) == 2
        assert reranked[0].doc_id == "d2"
        assert reranked[0].score == 0.99
        assert reranked[0].metadata["reranker_model"] == "test_model"
        assert reranked[0].retrieval_method == "reranked_vector"

    def test_reranker_empty_results(self):
        reranker = Reranker()
        assert reranker.rerank("query", []) == []

    def test_reranker_top_k(self):
        reranker = Reranker(top_k=1)
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
                retrieval_method="vector",
            ),
        ]
        reranked = reranker.rerank("query", results)
        assert len(reranked) == 1

    def test_reranker_from_config(self):
        config = {"model_name": "bge-reranker", "top_k": 5}
        reranker = Reranker.from_config(config)
        assert reranker.model_name == "bge-reranker"
        assert reranker.top_k == 5


class TestMultiWayRetriever:
    def test_retrieve_single_method(self):
        mock_store = type(
            "MockStore",
            (),
            {
                "search": lambda self, **kwargs: [
                    SearchResult(
                        content="a",
                        score=0.9,
                        doc_id="d1",
                        metadata={},
                        retrieval_method="fulltext",
                    ),
                ]
            },
        )()

        retriever = MultiWayRetriever(data_store=mock_store)
        results = retriever.retrieve("col", "query", methods=["fulltext"])

        assert len(results) == 1
        assert results[0].doc_id == "d1"

    def test_retrieve_multiple_methods(self):
        class MockStore:
            def search(self, **kwargs):
                method = kwargs.get("search_method")
                if method == "semantic":
                    return [
                        SearchResult(
                            content="a",
                            score=0.9,
                            doc_id="d1",
                            metadata={},
                            retrieval_method="vector",
                        ),
                    ]
                return [
                    SearchResult(
                        content="b",
                        score=0.8,
                        doc_id="d2",
                        metadata={},
                        retrieval_method="fulltext",
                    ),
                ]

        retriever = MultiWayRetriever(data_store=MockStore())
        results = retriever.retrieve(
            "col", "query", query_vector=[1.0, 0.0], methods=["vector", "fulltext"]
        )

        assert len(results) >= 1

    def test_retrieve_with_reranker(self):
        class MockStore:
            def search(self, **kwargs):
                return [
                    SearchResult(
                        content="a",
                        score=0.9,
                        doc_id="d1",
                        metadata={},
                        retrieval_method="fulltext",
                    ),
                    SearchResult(
                        content="b",
                        score=0.8,
                        doc_id="d2",
                        metadata={},
                        retrieval_method="fulltext",
                    ),
                ]

        reranker = Reranker(top_k=1)
        retriever = MultiWayRetriever(data_store=MockStore(), reranker=reranker)
        results = retriever.retrieve("col", "query", methods=["fulltext"], top_k=5)

        assert len(results) == 1

    def test_retrieve_no_methods(self):
        class MockStore:
            def search(self, **kwargs):
                return []

        retriever = MultiWayRetriever(data_store=MockStore())
        results = retriever.retrieve("col", "query", methods=[])
        assert results == []

    def test_retrieve_vector_without_query_vector(self):
        class MockStore:
            def search(self, **kwargs):
                return []

        retriever = MultiWayRetriever(data_store=MockStore())
        results = retriever.retrieve("col", "query", methods=["vector"])
        assert results == []

    def test_retrieve_with_score_threshold(self):
        class MockStore:
            def search(self, **kwargs):
                return [
                    SearchResult(
                        content="a",
                        score=0.95,
                        doc_id="d1",
                        metadata={},
                        retrieval_method="fulltext",
                    ),
                ]

        retriever = MultiWayRetriever(data_store=MockStore())
        results = retriever.retrieve(
            "col", "query", methods=["fulltext"], score_threshold=0.9
        )
        assert len(results) == 1
