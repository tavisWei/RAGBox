from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from api.core.rag.datasource.unified.base_data_store import SearchResult


class Reranker:
    """
    Reranker integration for post-processing retrieval results.

    Supports pluggable reranking backends. By default uses a no-op
    pass-through. Actual reranker implementations (BGE, Cohere, etc.)
    can be injected via the `rerank_fn` callback.
    """

    def __init__(
        self,
        rerank_fn: Optional[Callable[[str, List[SearchResult]], List[tuple]]] = None,
        model_name: str = "noop",
        top_k: int = 10,
    ):
        self.rerank_fn = rerank_fn
        self.model_name = model_name
        self.top_k = top_k

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        """
        Rerank search results for a given query.

        Args:
            query: The original query string.
            results: List of SearchResult to rerank.

        Returns:
            Reranked list of SearchResult sorted by new score descending.
        """
        if not results:
            return []

        if self.rerank_fn is None:
            return results[: self.top_k]

        reranked = self.rerank_fn(query, results)

        new_results = []
        for item in reranked:
            if isinstance(item, tuple) and len(item) >= 2:
                result, score = item[0], float(item[1])
            elif isinstance(item, SearchResult):
                result, score = item, item.score
            else:
                continue

            new_results.append(
                SearchResult(
                    content=result.content,
                    score=score,
                    doc_id=result.doc_id,
                    metadata={
                        **result.metadata,
                        "reranker_model": self.model_name,
                    },
                    retrieval_method=f"reranked_{result.retrieval_method}",
                )
            )

        new_results.sort(key=lambda x: x.score, reverse=True)
        return new_results[: self.top_k]

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Reranker":
        """Create a Reranker instance from a configuration dictionary."""
        return cls(
            rerank_fn=config.get("rerank_fn"),
            model_name=config.get("model_name", "noop"),
            top_k=config.get("top_k", 10),
        )
