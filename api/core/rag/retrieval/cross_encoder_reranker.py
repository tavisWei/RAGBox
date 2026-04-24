from typing import List, Optional
from .reranker import Reranker
from api.core.rag.datasource.unified.base_data_store import SearchResult


class CrossEncoderReranker(Reranker):
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        top_k: int = 10,
        device: Optional[str] = None,
    ):
        super().__init__(rerank_fn=None, model_name=model_name, top_k=top_k)
        self._model = None
        self._device = device
        self._model_name = model_name

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name, device=self._device)
        except ImportError:
            raise ImportError("CrossEncoderReranker requires sentence-transformers")

    def rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        if not results or len(results) <= 1:
            return results

        try:
            self._load_model()
            pairs = [(query, r.content) for r in results]
            scores = self._model.predict(pairs)

            scored_results = list(zip(results, scores))
            scored_results.sort(key=lambda x: x[1], reverse=True)

            reranked = []
            for result, score in scored_results[: self.top_k]:
                reranked.append(
                    SearchResult(
                        content=result.content,
                        score=float(score),
                        doc_id=result.doc_id,
                        metadata={
                            **result.metadata,
                            "original_score": result.score,
                            "reranker_model": self._model_name,
                        },
                        retrieval_method=f"reranked_{result.retrieval_method}",
                    )
                )
            return reranked
        except Exception:
            return results[: self.top_k]

    @classmethod
    def from_config(cls, config: dict) -> "CrossEncoderReranker":
        return cls(
            model_name=config.get("model_name", "BAAI/bge-reranker-base"),
            top_k=config.get("top_k", 10),
            device=config.get("device"),
        )
