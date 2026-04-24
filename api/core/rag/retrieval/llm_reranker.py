from typing import List, Optional, Callable
from .reranker import Reranker
from api.core.rag.datasource.unified.base_data_store import SearchResult


class LLMListwiseReranker(Reranker):
    def __init__(
        self,
        llm_function: Callable,
        model_name: str = "gpt-3.5-turbo",
        top_k: int = 10,
        batch_size: int = 20,
    ):
        super().__init__(rerank_fn=None, model_name=model_name, top_k=top_k)
        self.llm_function = llm_function
        self.batch_size = batch_size

    def rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        if not results or len(results) <= 1:
            return results

        all_reranked = []
        for i in range(0, len(results), self.batch_size):
            batch = results[i : i + self.batch_size]
            reranked_batch = self._rerank_batch(query, batch)
            all_reranked.extend(reranked_batch)

        all_reranked.sort(key=lambda x: x.score, reverse=True)
        return all_reranked[: self.top_k]

    def _rerank_batch(
        self, query: str, results: List[SearchResult]
    ) -> List[SearchResult]:
        doc_list = "\n".join(
            [f"{i + 1}. {r.content[:200]}" for i, r in enumerate(results)]
        )

        prompt = f"""Rank these documents by relevance to: "{query}"

Documents:
{doc_list}

Return only the numbers in order of relevance (most relevant first), separated by commas."""

        try:
            response = self.llm_function(prompt)
            ranked_indices = self._parse_ranking(response, len(results))

            reranked = []
            for rank, idx in enumerate(ranked_indices):
                if 0 <= idx < len(results):
                    result = results[idx]
                    reranked.append(
                        SearchResult(
                            content=result.content,
                            score=1.0 - (rank * 0.1),
                            doc_id=result.doc_id,
                            metadata={**result.metadata, "llm_rank": rank + 1},
                            retrieval_method=f"llm_reranked_{result.retrieval_method}",
                        )
                    )
            return reranked
        except Exception:
            return results

    def _parse_ranking(self, response: str, max_index: int) -> List[int]:
        import re

        numbers = re.findall(r"\d+", response)
        indices = [int(n) - 1 for n in numbers]
        return [i for i in indices if 0 <= i < max_index]

    @classmethod
    def from_config(cls, config: dict, llm_function: Callable) -> "LLMListwiseReranker":
        return cls(
            llm_function=llm_function,
            model_name=config.get("model_name", "gpt-3.5-turbo"),
            top_k=config.get("top_k", 10),
        )
