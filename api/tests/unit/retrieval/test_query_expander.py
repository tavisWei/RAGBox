import pytest
from unittest.mock import MagicMock

from api.core.rag.retrieval.query_expander import QueryExpander, ExpandedQuery
from api.core.rag.retrieval.retrieval_config import QueryExpansionMode


class TestExpandedQuery:
    def test_creation(self):
        eq = ExpandedQuery(
            query="test query",
            original="test",
            expansion_type="multi_query",
            score=0.8,
        )
        assert eq.query == "test query"
        assert eq.original == "test"
        assert eq.expansion_type == "multi_query"
        assert eq.score == 0.8

    def test_default_score(self):
        eq = ExpandedQuery(query="test", original="test", expansion_type="original")
        assert eq.score == 1.0


class TestQueryExpander:
    def test_initialization_with_defaults(self):
        expander = QueryExpander()
        assert expander.mode == QueryExpansionMode.NONE
        assert expander.llm_function is None
        assert expander.expansion_count == 3

    def test_initialization_with_custom_params(self):
        mock_llm = MagicMock()
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=5,
        )
        assert expander.mode == QueryExpansionMode.MULTI_QUERY
        assert expander.llm_function == mock_llm
        assert expander.expansion_count == 5

    def test_expand_none_mode(self):
        expander = QueryExpander(mode=QueryExpansionMode.NONE)
        results = expander.expand("test query")

        assert len(results) == 1
        assert results[0].query == "test query"
        assert results[0].original == "test query"
        assert results[0].expansion_type == "original"
        assert results[0].score == 1.0

    def test_expand_multi_query_without_llm(self):
        expander = QueryExpander(mode=QueryExpansionMode.MULTI_QUERY)
        results = expander.expand("test query")

        assert len(results) == 1
        assert results[0].expansion_type == "original"

    def test_expand_multi_query_with_llm(self):
        mock_llm = MagicMock(return_value="variant 1\nvariant 2\nvariant 3")
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=3,
        )
        results = expander.expand("original query")

        assert len(results) == 4
        assert results[0].expansion_type == "original"
        assert results[1].expansion_type == "multi_query"
        assert results[1].score == pytest.approx(0.8, abs=1e-6)
        assert results[2].score == pytest.approx(0.7, abs=1e-6)
        assert results[3].score == pytest.approx(0.6, abs=1e-6)

    def test_expand_multi_query_llm_error(self):
        mock_llm = MagicMock(side_effect=Exception("LLM error"))
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
        )
        results = expander.expand("test query")

        assert len(results) == 1
        assert results[0].expansion_type == "original"

    def test_expand_hyde_without_llm(self):
        expander = QueryExpander(mode=QueryExpansionMode.HYDE)
        results = expander.expand("test query")

        assert len(results) == 1
        assert results[0].expansion_type == "original"

    def test_expand_hyde_with_llm(self):
        mock_llm = MagicMock(return_value="This is a hypothetical document.")
        expander = QueryExpander(
            mode=QueryExpansionMode.HYDE,
            llm_function=mock_llm,
        )
        results = expander.expand("test query")

        assert len(results) == 2
        assert results[0].expansion_type == "original"
        assert results[1].expansion_type == "hyde"
        assert results[1].query == "This is a hypothetical document."
        assert results[1].score == 0.9

    def test_expand_hyde_llm_error(self):
        mock_llm = MagicMock(side_effect=Exception("LLM error"))
        expander = QueryExpander(
            mode=QueryExpansionMode.HYDE,
            llm_function=mock_llm,
        )
        results = expander.expand("test query")

        assert len(results) == 1
        assert results[0].expansion_type == "original"

    def test_multi_query_prompt_format(self):
        mock_llm = MagicMock(return_value="q1\nq2\nq3")
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=3,
        )
        expander.expand("search term")

        call_args = mock_llm.call_args[0][0]
        assert "search term" in call_args
        assert "Generate 3 different search queries" in call_args

    def test_hyde_prompt_format(self):
        mock_llm = MagicMock(return_value="hypothetical doc")
        expander = QueryExpander(
            mode=QueryExpansionMode.HYDE,
            llm_function=mock_llm,
        )
        expander.expand("search term")

        call_args = mock_llm.call_args[0][0]
        assert "search term" in call_args
        assert "hypothetical document" in call_args

    def test_multi_query_deduplicates_original(self):
        mock_llm = MagicMock(return_value="test query\nvariant 1\nvariant 2")
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=3,
        )
        results = expander.expand("test query")

        queries = [r.query for r in results]
        assert queries.count("test query") == 1

    def test_multi_query_limits_count(self):
        mock_llm = MagicMock(return_value="\n".join([f"q{i}" for i in range(10)]))
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=3,
        )
        results = expander.expand("test")

        assert len(results) <= 4

    def test_multi_query_empty_lines_filtered(self):
        mock_llm = MagicMock(return_value="q1\n\n\nq2\n  \nq3")
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=5,
        )
        results = expander.expand("test")

        for r in results[1:]:
            assert r.query.strip() != ""

    def test_unknown_mode_fallback(self):
        expander = QueryExpander()
        expander.mode = "unknown"
        results = expander.expand("test query")

        assert len(results) == 1
        assert results[0].expansion_type == "original"

    def test_expand_empty_query(self):
        expander = QueryExpander(mode=QueryExpansionMode.NONE)
        results = expander.expand("")

        assert len(results) == 1
        assert results[0].query == ""

    def test_hyde_returns_document(self):
        doc = "RAG systems combine retrieval and generation."
        mock_llm = MagicMock(return_value=doc)
        expander = QueryExpander(
            mode=QueryExpansionMode.HYDE,
            llm_function=mock_llm,
        )
        results = expander.expand("What is RAG?")

        assert results[1].query == doc
        assert results[1].original == "What is RAG?"

    def test_multi_query_score_decrements(self):
        mock_llm = MagicMock(return_value="q1\nq2\nq3")
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=3,
        )
        results = expander.expand("test")

        assert results[1].score == pytest.approx(0.8, abs=1e-6)
        assert results[2].score == pytest.approx(0.7, abs=1e-6)
        assert results[3].score == pytest.approx(0.6, abs=1e-6)

    def test_expansion_count_zero(self):
        mock_llm = MagicMock(return_value="q1")
        expander = QueryExpander(
            mode=QueryExpansionMode.MULTI_QUERY,
            llm_function=mock_llm,
            expansion_count=0,
        )
        results = expander.expand("test")

        assert len(results) == 1
