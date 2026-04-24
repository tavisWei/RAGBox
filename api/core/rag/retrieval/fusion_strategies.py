from __future__ import annotations

from typing import List

from api.core.rag.datasource.unified.base_data_store import SearchResult


def reciprocal_rank_fusion(
    result_lists: List[List[SearchResult]],
    k: float = 60.0,
) -> List[SearchResult]:
    """
    Reciprocal Rank Fusion (RRF) algorithm.

    Combines multiple ranked result lists into a single fused ranking.
    Score = sum(1 / (k + rank)) for each list where the document appears.

    Args:
        result_lists: Multiple lists of SearchResult, each from a different retrieval method.
        k: RRF constant (default 60), higher values reduce the impact of ranking differences.

    Returns:
        Fused list of SearchResult sorted by RRF score descending.
    """
    scores: dict = {}
    doc_map: dict = {}

    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            doc_id = result.doc_id
            if doc_id not in scores:
                scores[doc_id] = 0.0
                doc_map[doc_id] = result
            scores[doc_id] += 1.0 / (k + rank)

    fused = []
    for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        result = doc_map[doc_id]
        fused.append(
            SearchResult(
                content=result.content,
                score=score,
                doc_id=doc_id,
                metadata=result.metadata,
                retrieval_method="fusion_rrf",
            )
        )

    return fused


def weighted_score_fusion(
    result_lists: List[List[SearchResult]],
    weights: List[float],
) -> List[SearchResult]:
    """
    Weighted score fusion algorithm.

    Combines multiple result lists by weighting each list's scores.
    Final score = sum(weight_i * normalized_score_i).

    Args:
        result_lists: Multiple lists of SearchResult.
        weights: Weight for each result list. Must sum to 1.0 (not enforced).

    Returns:
        Fused list of SearchResult sorted by weighted score descending.
    """
    if len(result_lists) != len(weights):
        raise ValueError(
            f"Number of result lists ({len(result_lists)}) must match "
            f"number of weights ({len(weights)})"
        )

    scores: dict = {}
    doc_map: dict = {}

    for results, weight in zip(result_lists, weights):
        if not results:
            continue

        max_score = max(r.score for r in results) if results else 1.0
        min_score = min(r.score for r in results) if results else 0.0
        score_range = max_score - min_score if max_score > min_score else 1.0

        for result in results:
            doc_id = result.doc_id
            if doc_id not in scores:
                scores[doc_id] = 0.0
                doc_map[doc_id] = result

            normalized = (result.score - min_score) / score_range
            scores[doc_id] += weight * normalized

    fused = []
    for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        result = doc_map[doc_id]
        fused.append(
            SearchResult(
                content=result.content,
                score=score,
                doc_id=doc_id,
                metadata=result.metadata,
                retrieval_method="fusion_weighted",
            )
        )

    return fused
