from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RetrievalMethod(str, Enum):
    SEMANTIC = "semantic"
    FULLTEXT = "fulltext"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class FusionMode(str, Enum):
    RRF = "rrf"
    WEIGHTED = "weighted"
    SIMPLE = "simple"


class RerankMode(str, Enum):
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    LLM_LISTWISE = "llm_listwise"


class QueryExpansionMode(str, Enum):
    NONE = "none"
    MULTI_QUERY = "multi_query"
    HYDE = "hyde"


@dataclass
class RetrievalConfig:
    methods: List[RetrievalMethod] = field(
        default_factory=lambda: [RetrievalMethod.HYBRID]
    )
    top_k: int = 10
    score_threshold: Optional[float] = None
    fusion_mode: FusionMode = FusionMode.RRF
    fusion_weights: Optional[Dict[str, float]] = None
    query_expansion: QueryExpansionMode = QueryExpansionMode.NONE
    expansion_count: int = 3
    rerank_mode: RerankMode = RerankMode.NONE
    rerank_model: Optional[str] = None
    rerank_top_n: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def beginner(cls) -> "RetrievalConfig":
        return cls(
            methods=[RetrievalMethod.SEMANTIC],
            top_k=5,
            fusion_mode=FusionMode.SIMPLE,
            query_expansion=QueryExpansionMode.NONE,
            rerank_mode=RerankMode.NONE,
        )

    @classmethod
    def intermediate(cls) -> "RetrievalConfig":
        return cls(
            methods=[RetrievalMethod.HYBRID],
            top_k=10,
            fusion_mode=FusionMode.RRF,
            query_expansion=QueryExpansionMode.NONE,
            rerank_mode=RerankMode.NONE,
        )

    @classmethod
    def advanced(cls) -> "RetrievalConfig":
        return cls(
            methods=[RetrievalMethod.HYBRID],
            top_k=20,
            fusion_mode=FusionMode.RRF,
            query_expansion=QueryExpansionMode.MULTI_QUERY,
            expansion_count=3,
            rerank_mode=RerankMode.CROSS_ENCODER,
            rerank_top_n=10,
        )

    @classmethod
    def expert(cls) -> "RetrievalConfig":
        return cls(
            methods=[RetrievalMethod.HYBRID],
            top_k=30,
            fusion_mode=FusionMode.WEIGHTED,
            fusion_weights={"semantic": 0.6, "fulltext": 0.4},
            query_expansion=QueryExpansionMode.HYDE,
            expansion_count=3,
            rerank_mode=RerankMode.LLM_LISTWISE,
            rerank_top_n=10,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "methods": [m.value for m in self.methods],
            "top_k": self.top_k,
            "score_threshold": self.score_threshold,
            "fusion_mode": self.fusion_mode.value,
            "fusion_weights": self.fusion_weights,
            "query_expansion": self.query_expansion.value,
            "expansion_count": self.expansion_count,
            "rerank_mode": self.rerank_mode.value,
            "rerank_model": self.rerank_model,
            "rerank_top_n": self.rerank_top_n,
            "filters": self.filters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalConfig":
        return cls(
            methods=[
                RetrievalMethod(m)
                for m in data.get("methods", [RetrievalMethod.HYBRID.value])
            ],
            top_k=data.get("top_k", 10),
            score_threshold=data.get("score_threshold"),
            fusion_mode=FusionMode(data.get("fusion_mode", FusionMode.RRF.value)),
            fusion_weights=data.get("fusion_weights"),
            query_expansion=QueryExpansionMode(
                data.get("query_expansion", QueryExpansionMode.NONE.value)
            ),
            expansion_count=data.get("expansion_count", 3),
            rerank_mode=RerankMode(data.get("rerank_mode", RerankMode.NONE.value)),
            rerank_model=data.get("rerank_model"),
            rerank_top_n=data.get("rerank_top_n", 10),
            filters=data.get("filters", {}),
        )
