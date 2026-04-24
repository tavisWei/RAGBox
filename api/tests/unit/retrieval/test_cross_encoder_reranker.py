import pytest
from unittest.mock import MagicMock, patch

from api.core.rag.retrieval.cross_encoder_reranker import CrossEncoderReranker
from api.core.rag.datasource.unified.base_data_store import SearchResult


class TestCrossEncoderReranker:
    def test_initialization_with_defaults(self):
        reranker = CrossEncoderReranker()
        assert reranker._model_name == "BAAI/bge-reranker-base"
        assert reranker.top_k == 10
        assert reranker._device is None
        assert reranker._model is None

    def test_initialization_with_custom_params(self):
        reranker = CrossEncoderReranker(
            model_name="custom-model",
            top_k=5,
            device="cuda",
        )
        assert reranker._model_name == "custom-model"
        assert reranker.top_k == 5
        assert reranker._device == "cuda"

    def test_load_model(self):
        reranker = CrossEncoderReranker()

        mock_ce = MagicMock()
        mock_model = MagicMock()
        mock_ce.return_value = mock_model

        with patch.dict(
            "sys.modules", {"sentence_transformers": MagicMock(CrossEncoder=mock_ce)}
        ):
            reranker._load_model()

            mock_ce.assert_called_once_with("BAAI/bge-reranker-base", device=None)
            assert reranker._model == mock_model

    def test_load_model_only_once(self):
        reranker = CrossEncoderReranker()
        reranker._model = MagicMock()

        mock_ce = MagicMock()
        with patch.dict(
            "sys.modules", {"sentence_transformers": MagicMock(CrossEncoder=mock_ce)}
        ):
            reranker._load_model()
            mock_ce.assert_not_called()

    def test_load_model_import_error(self):
        reranker = CrossEncoderReranker()

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers"):
                reranker._load_model()

    def test_rerank_empty_results(self):
        reranker = CrossEncoderReranker()
        results = reranker.rerank("query", [])
        assert results == []

    def test_rerank_single_result(self):
        reranker = CrossEncoderReranker()
        single = SearchResult(
            content="content",
            score=0.8,
            doc_id="doc1",
            metadata={},
            retrieval_method="semantic",
        )
        results = reranker.rerank("query", [single])

        assert len(results) == 1
        assert results[0].doc_id == "doc1"

    def test_rerank_successful(self):
        reranker = CrossEncoderReranker(top_k=2)

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.3, 0.9, 0.5]
        reranker._model = mock_model

        results = [
            SearchResult(
                content="c1",
                score=0.5,
                doc_id="doc1",
                metadata={"orig": "data"},
                retrieval_method="semantic",
            ),
            SearchResult(
                content="c2",
                score=0.6,
                doc_id="doc2",
                metadata={"orig": "data"},
                retrieval_method="semantic",
            ),
            SearchResult(
                content="c3",
                score=0.7,
                doc_id="doc3",
                metadata={"orig": "data"},
                retrieval_method="semantic",
            ),
        ]

        reranked = reranker.rerank("query", results)

        assert len(reranked) == 2
        assert reranked[0].doc_id == "doc2"
        assert reranked[0].score == pytest.approx(0.9, abs=1e-6)
        assert reranked[1].doc_id == "doc3"
        assert reranked[1].score == pytest.approx(0.5, abs=1e-6)

    def test_rerank_preserves_metadata(self):
        reranker = CrossEncoderReranker(top_k=1)

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9]
        reranker._model = mock_model

        results = [
            SearchResult(
                content="content",
                score=0.5,
                doc_id="doc1",
                metadata={"source": "test"},
                retrieval_method="semantic",
            ),
            SearchResult(
                content="content2",
                score=0.4,
                doc_id="doc2",
                metadata={"source": "test2"},
                retrieval_method="semantic",
            ),
        ]

        reranked = reranker.rerank("query", results)

        assert reranked[0].metadata["source"] == "test"
        assert reranked[0].metadata.get("original_score") == 0.5
        assert reranked[0].metadata.get("reranker_model") == "BAAI/bge-reranker-base"

    def test_rerank_updates_retrieval_method(self):
        reranker = CrossEncoderReranker(top_k=1)

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.3]
        reranker._model = mock_model

        results = [
            SearchResult(
                content="content",
                score=0.5,
                doc_id="doc1",
                metadata={},
                retrieval_method="semantic",
            ),
            SearchResult(
                content="content2",
                score=0.4,
                doc_id="doc2",
                metadata={},
                retrieval_method="semantic",
            ),
        ]

        reranked = reranker.rerank("query", results)

        assert reranked[0].retrieval_method.startswith("reranked_")

    def test_rerank_on_error_returns_topk(self):
        reranker = CrossEncoderReranker(top_k=2)

        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("Model error")
        reranker._model = mock_model

        results = [
            SearchResult(
                content="c1",
                score=0.5,
                doc_id="doc1",
                metadata={},
                retrieval_method="semantic",
            ),
            SearchResult(
                content="c2",
                score=0.6,
                doc_id="doc2",
                metadata={},
                retrieval_method="semantic",
            ),
            SearchResult(
                content="c3",
                score=0.7,
                doc_id="doc3",
                metadata={},
                retrieval_method="semantic",
            ),
        ]

        reranked = reranker.rerank("query", results)

        assert len(reranked) == 2

    def test_rerank_respects_top_k(self):
        reranker = CrossEncoderReranker(top_k=3)

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
        reranker._model = mock_model

        results = [
            SearchResult(
                content=f"c{i}",
                score=0.5,
                doc_id=f"doc{i}",
                metadata={},
                retrieval_method="semantic",
            )
            for i in range(5)
        ]

        reranked = reranker.rerank("query", results)

        assert len(reranked) == 3

    def test_from_config(self):
        config = {
            "model_name": "custom-model",
            "top_k": 15,
            "device": "cpu",
        }
        reranker = CrossEncoderReranker.from_config(config)

        assert isinstance(reranker, CrossEncoderReranker)
        assert reranker._model_name == "custom-model"
        assert reranker.top_k == 15
        assert reranker._device == "cpu"

    def test_from_config_defaults(self):
        config = {}
        reranker = CrossEncoderReranker.from_config(config)

        assert reranker._model_name == "BAAI/bge-reranker-base"
        assert reranker.top_k == 10
        assert reranker._device is None

    def test_rerank_pairs_passed_to_model(self):
        reranker = CrossEncoderReranker()

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.5]
        reranker._model = mock_model

        results = [
            SearchResult(
                content="test content",
                score=0.5,
                doc_id="doc1",
                metadata={},
                retrieval_method="semantic",
            ),
        ]

        reranked = reranker.rerank("test query", results)

        assert len(reranked) == 1
        assert reranked[0].score == pytest.approx(0.5, abs=1e-6)

    def test_rerank_score_is_float(self):
        reranker = CrossEncoderReranker()

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9]
        reranker._model = mock_model

        results = [
            SearchResult(
                content="content",
                score=0.5,
                doc_id="doc1",
                metadata={},
                retrieval_method="semantic",
            ),
        ]

        reranked = reranker.rerank("query", results)

        assert isinstance(reranked[0].score, float)

    def test_rerank_with_large_batch(self):
        reranker = CrossEncoderReranker(top_k=5)

        mock_model = MagicMock()
        mock_model.predict.return_value = list(range(100, 0, -1))
        reranker._model = mock_model

        results = [
            SearchResult(
                content=f"content{i}",
                score=0.5,
                doc_id=f"doc{i}",
                metadata={},
                retrieval_method="semantic",
            )
            for i in range(100)
        ]

        reranked = reranker.rerank("query", results)

        assert len(reranked) == 5
        assert reranked[0].score == 100.0
