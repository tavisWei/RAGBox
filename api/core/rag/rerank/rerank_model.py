from typing import Any, List, Optional

from api.core.rag.models.document import Document
from api.core.rag.rerank.rerank_base import BaseRerankRunner


class RerankModelRunner(BaseRerankRunner):
    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        self.model_name = model_name or "default-reranker"
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = kwargs.get("timeout", 30)
        self.max_retries = kwargs.get("max_retries", 3)

    def run(
        self,
        query: str,
        documents: List[Document],
        score_threshold: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> List[Document]:
        if not documents:
            return []

        scores = self._call_rerank_model(query, documents)

        for i, doc in enumerate(documents):
            doc.metadata = {
                **(doc.metadata or {}),
                "rerank_score": scores[i],
            }

        reranked = sorted(
            documents,
            key=lambda d: d.metadata.get("rerank_score", 0.0),
            reverse=True,
        )

        if score_threshold is not None:
            reranked = [
                d
                for d in reranked
                if d.metadata.get("rerank_score", 0.0) >= score_threshold
            ]

        if top_n is not None:
            reranked = reranked[:top_n]

        return reranked

    def _call_rerank_model(self, query: str, documents: List[Document]) -> List[float]:
        return [0.5] * len(documents)
