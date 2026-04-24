"""Unit tests for retrieval configuration classes."""

import pytest

from api.core.rag.retrieval.retrieval_config import (
    RetrievalMethod,
    FusionMode,
    RerankMode,
    QueryExpansionMode,
    RetrievalConfig,
)


class TestRetrievalMethod:
    """Test RetrievalMethod enum."""

    def test_enum_values(self):
        assert RetrievalMethod.SEMANTIC == "semantic"
        assert RetrievalMethod.FULLTEXT == "fulltext"
        assert RetrievalMethod.KEYWORD == "keyword"
        assert RetrievalMethod.HYBRID == "hybrid"

    def test_enum_membership(self):
        assert "semantic" in [m.value for m in RetrievalMethod]
        assert "fulltext" in [m.value for m in RetrievalMethod]
        assert "keyword" in [m.value for m in RetrievalMethod]
        assert "hybrid" in [m.value for m in RetrievalMethod]


class TestFusionMode:
    """Test FusionMode enum."""

    def test_enum_values(self):
        assert FusionMode.RRF == "rrf"
        assert FusionMode.WEIGHTED == "weighted"
        assert FusionMode.SIMPLE == "simple"


class TestRerankMode:
    """Test RerankMode enum."""

    def test_enum_values(self):
        assert RerankMode.NONE == "none"
        assert RerankMode.CROSS_ENCODER == "cross_encoder"
        assert RerankMode.LLM_LISTWISE == "llm_listwise"


class TestQueryExpansionMode:
    """Test QueryExpansionMode enum."""

    def test_enum_values(self):
        assert QueryExpansionMode.NONE == "none"
        assert QueryExpansionMode.MULTI_QUERY == "multi_query"
        assert QueryExpansionMode.HYDE == "hyde"


class TestRetrievalConfig:
    """Test RetrievalConfig dataclass."""

    def test_default_initialization(self):
        """Should initialize with default values."""
        config = RetrievalConfig()

        assert config.methods == [RetrievalMethod.HYBRID]
        assert config.top_k == 10
        assert config.score_threshold is None
        assert config.fusion_mode == FusionMode.RRF
        assert config.fusion_weights is None
        assert config.query_expansion == QueryExpansionMode.NONE
        assert config.expansion_count == 3
        assert config.rerank_mode == RerankMode.NONE
        assert config.rerank_model is None
        assert config.rerank_top_n == 10
        assert config.filters == {}

    def test_custom_initialization(self):
        """Should initialize with custom values."""
        config = RetrievalConfig(
            methods=[RetrievalMethod.SEMANTIC],
            top_k=5,
            score_threshold=0.8,
            fusion_mode=FusionMode.SIMPLE,
            query_expansion=QueryExpansionMode.MULTI_QUERY,
            expansion_count=5,
            rerank_mode=RerankMode.CROSS_ENCODER,
            rerank_model="bge-reranker",
            rerank_top_n=20,
            filters={"category": "tech"},
        )

        assert config.methods == [RetrievalMethod.SEMANTIC]
        assert config.top_k == 5
        assert config.score_threshold == 0.8
        assert config.fusion_mode == FusionMode.SIMPLE
        assert config.query_expansion == QueryExpansionMode.MULTI_QUERY
        assert config.expansion_count == 5
        assert config.rerank_mode == RerankMode.CROSS_ENCODER
        assert config.rerank_model == "bge-reranker"
        assert config.rerank_top_n == 20
        assert config.filters == {"category": "tech"}

    def test_beginner_preset(self):
        """Should create beginner preset config."""
        config = RetrievalConfig.beginner()

        assert config.methods == [RetrievalMethod.SEMANTIC]
        assert config.top_k == 5
        assert config.fusion_mode == FusionMode.SIMPLE
        assert config.query_expansion == QueryExpansionMode.NONE
        assert config.rerank_mode == RerankMode.NONE

    def test_intermediate_preset(self):
        """Should create intermediate preset config."""
        config = RetrievalConfig.intermediate()

        assert config.methods == [RetrievalMethod.HYBRID]
        assert config.top_k == 10
        assert config.fusion_mode == FusionMode.RRF
        assert config.query_expansion == QueryExpansionMode.NONE
        assert config.rerank_mode == RerankMode.NONE

    def test_advanced_preset(self):
        """Should create advanced preset config."""
        config = RetrievalConfig.advanced()

        assert config.methods == [RetrievalMethod.HYBRID]
        assert config.top_k == 20
        assert config.fusion_mode == FusionMode.RRF
        assert config.query_expansion == QueryExpansionMode.MULTI_QUERY
        assert config.expansion_count == 3
        assert config.rerank_mode == RerankMode.CROSS_ENCODER
        assert config.rerank_top_n == 10

    def test_expert_preset(self):
        """Should create expert preset config."""
        config = RetrievalConfig.expert()

        assert config.methods == [RetrievalMethod.HYBRID]
        assert config.top_k == 30
        assert config.fusion_mode == FusionMode.WEIGHTED
        assert config.fusion_weights == {"semantic": 0.6, "fulltext": 0.4}
        assert config.query_expansion == QueryExpansionMode.HYDE
        assert config.expansion_count == 3
        assert config.rerank_mode == RerankMode.LLM_LISTWISE
        assert config.rerank_top_n == 10

    def test_to_dict(self):
        """Should serialize to dictionary."""
        config = RetrievalConfig(
            methods=[RetrievalMethod.SEMANTIC, RetrievalMethod.KEYWORD],
            top_k=15,
            score_threshold=0.7,
            fusion_mode=FusionMode.WEIGHTED,
            fusion_weights={"semantic": 0.7, "keyword": 0.3},
            query_expansion=QueryExpansionMode.MULTI_QUERY,
            expansion_count=4,
            rerank_mode=RerankMode.CROSS_ENCODER,
            rerank_model="model-v1",
            rerank_top_n=5,
            filters={"lang": "en"},
        )
        data = config.to_dict()

        assert data["methods"] == ["semantic", "keyword"]
        assert data["top_k"] == 15
        assert data["score_threshold"] == 0.7
        assert data["fusion_mode"] == "weighted"
        assert data["fusion_weights"] == {"semantic": 0.7, "keyword": 0.3}
        assert data["query_expansion"] == "multi_query"
        assert data["expansion_count"] == 4
        assert data["rerank_mode"] == "cross_encoder"
        assert data["rerank_model"] == "model-v1"
        assert data["rerank_top_n"] == 5
        assert data["filters"] == {"lang": "en"}

    def test_from_dict(self):
        """Should deserialize from dictionary."""
        data = {
            "methods": ["semantic", "fulltext"],
            "top_k": 25,
            "score_threshold": 0.6,
            "fusion_mode": "rrf",
            "fusion_weights": None,
            "query_expansion": "hyde",
            "expansion_count": 5,
            "rerank_mode": "llm_listwise",
            "rerank_model": "gpt-4",
            "rerank_top_n": 15,
            "filters": {"category": "docs"},
        }
        config = RetrievalConfig.from_dict(data)

        assert config.methods == [RetrievalMethod.SEMANTIC, RetrievalMethod.FULLTEXT]
        assert config.top_k == 25
        assert config.score_threshold == 0.6
        assert config.fusion_mode == FusionMode.RRF
        assert config.fusion_weights is None
        assert config.query_expansion == QueryExpansionMode.HYDE
        assert config.expansion_count == 5
        assert config.rerank_mode == RerankMode.LLM_LISTWISE
        assert config.rerank_model == "gpt-4"
        assert config.rerank_top_n == 15
        assert config.filters == {"category": "docs"}

    def test_from_dict_defaults(self):
        """Should use defaults for missing keys."""
        data = {"top_k": 8}
        config = RetrievalConfig.from_dict(data)

        assert config.top_k == 8
        assert config.methods == [RetrievalMethod.HYBRID]
        assert config.fusion_mode == FusionMode.RRF
        assert config.expansion_count == 3
        assert config.rerank_top_n == 10

    def test_from_dict_empty(self):
        """Should use all defaults for empty dict."""
        config = RetrievalConfig.from_dict({})

        assert config.methods == [RetrievalMethod.HYBRID]
        assert config.top_k == 10
        assert config.fusion_mode == FusionMode.RRF

    def test_roundtrip_serialization(self):
        """Should survive roundtrip serialization."""
        original = RetrievalConfig.advanced()
        data = original.to_dict()
        restored = RetrievalConfig.from_dict(data)

        assert restored.methods == original.methods
        assert restored.top_k == original.top_k
        assert restored.fusion_mode == original.fusion_mode
        assert restored.query_expansion == original.query_expansion
        assert restored.rerank_mode == original.rerank_mode

    def test_multiple_methods(self):
        """Should support multiple retrieval methods."""
        config = RetrievalConfig(
            methods=[
                RetrievalMethod.SEMANTIC,
                RetrievalMethod.FULLTEXT,
                RetrievalMethod.KEYWORD,
            ]
        )

        assert len(config.methods) == 3
        assert RetrievalMethod.SEMANTIC in config.methods
        assert RetrievalMethod.FULLTEXT in config.methods
        assert RetrievalMethod.KEYWORD in config.methods

    def test_weighted_fusion_config(self):
        """Should support weighted fusion configuration."""
        config = RetrievalConfig(
            fusion_mode=FusionMode.WEIGHTED,
            fusion_weights={
                "semantic": 0.5,
                "fulltext": 0.3,
                "keyword": 0.2,
            },
        )

        assert config.fusion_mode == FusionMode.WEIGHTED
        assert config.fusion_weights["semantic"] == 0.5
        assert config.fusion_weights["fulltext"] == 0.3
        assert config.fusion_weights["keyword"] == 0.2

    def test_none_score_threshold(self):
        """Should allow None score_threshold."""
        config = RetrievalConfig(score_threshold=None)

        assert config.score_threshold is None

    def test_zero_score_threshold(self):
        """Should allow zero score_threshold."""
        config = RetrievalConfig(score_threshold=0.0)

        assert config.score_threshold == 0.0

    def test_preset_immutability(self):
        """Should create independent instances from presets."""
        c1 = RetrievalConfig.beginner()
        c2 = RetrievalConfig.beginner()

        c1.top_k = 99
        assert c2.top_k == 5

    def test_filters_mutation(self):
        """Should allow filters mutation."""
        config = RetrievalConfig()
        config.filters["new_key"] = "new_value"

        assert config.filters["new_key"] == "new_value"
