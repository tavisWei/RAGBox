from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from api.core.rag.datasource.unified.base_data_store import BaseDataStore, SearchResult
from api.core.rag.retrieval.fusion_strategies import reciprocal_rank_fusion
from api.core.rag.retrieval.retrieval_config import (
    RetrievalConfig,
    RetrievalMethod,
    FusionMode,
    RerankMode,
)
from api.core.rag.retrieval.query_expander import QueryExpander
from api.core.rag.retrieval.cross_encoder_reranker import CrossEncoderReranker
from api.core.rag.retrieval.llm_reranker import LLMListwiseReranker
from api.core.rag.retrieval.reranker import Reranker


class MultiWayRetriever:
    def __init__(
        self,
        data_store: BaseDataStore,
        config: Optional[RetrievalConfig] = None,
        llm_function: Optional[Callable] = None,
        fusion_method: str = "rrf",
        reranker: Optional[Reranker] = None,
        max_workers: int = 3,
    ):
        self.data_store = data_store
        self.config = config or RetrievalConfig.intermediate()
        self.llm_function = llm_function
        self.fusion_method = fusion_method
        self.reranker = reranker
        self.max_workers = max_workers
        self.query_expander = QueryExpander(
            mode=self.config.query_expansion,
            llm_function=llm_function,
            expansion_count=self.config.expansion_count,
        )

    def retrieve(
        self,
        collection_name: str,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
        methods: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        if methods is None and self.config.methods:
            methods = [m.value for m in self.config.methods]
        methods = methods or ["vector", "fulltext"]

        expanded_queries = self.query_expander.expand(query)

        all_result_lists = []
        for expanded in expanded_queries:
            tasks = self._build_tasks(
                collection_name,
                expanded.query,
                query_vector,
                self.config.top_k if self.config else top_k,
                self.config.score_threshold
                if self.config and self.config.score_threshold is not None
                else score_threshold,
                filters if filters else (self.config.filters if self.config else None),
                methods,
            )

            result_lists = self._execute_parallel(tasks)
            all_result_lists.extend(result_lists)

        if len(all_result_lists) == 1:
            fused = all_result_lists[0]
        elif len(all_result_lists) > 1:
            fused = self._fuse_results(all_result_lists)
        else:
            fused = []

        reranker = self.reranker
        if reranker is None and self.config:
            reranker = self._get_reranker_from_config()

        if reranker:
            fused = reranker.rerank(query, fused)

        final_top_k = self.config.top_k if self.config else top_k
        return fused[:final_top_k]

    def _get_reranker_from_config(self) -> Optional[Reranker]:
        if self.config.rerank_mode == RerankMode.CROSS_ENCODER:
            return CrossEncoderReranker.from_config(
                {
                    "model_name": self.config.rerank_model or "BAAI/bge-reranker-base",
                    "top_k": self.config.rerank_top_n,
                }
            )
        elif self.config.rerank_mode == RerankMode.LLM_LISTWISE:
            if self.llm_function:
                return LLMListwiseReranker.from_config(
                    {
                        "model_name": self.config.rerank_model or "gpt-3.5-turbo",
                        "top_k": self.config.rerank_top_n,
                    },
                    llm_function=self.llm_function,
                )
        return None

    def _build_tasks(
        self,
        collection_name: str,
        query: str,
        query_vector: Optional[List[float]],
        top_k: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
        methods: List[str],
    ) -> List[dict]:
        tasks = []
        for method in methods:
            if method in ("vector", "semantic") and query_vector is not None:
                tasks.append(
                    {
                        "collection_name": collection_name,
                        "method": "semantic",
                        "query": query,
                        "query_vector": query_vector,
                        "top_k": top_k,
                        "score_threshold": score_threshold,
                        "filters": filters,
                    }
                )
            elif method in ("keyword", "fulltext"):
                tasks.append(
                    {
                        "collection_name": collection_name,
                        "method": "fulltext",
                        "query": query,
                        "query_vector": None,
                        "top_k": top_k,
                        "score_threshold": score_threshold,
                        "filters": filters,
                    }
                )
            elif method == "hybrid":
                if query_vector is not None:
                    tasks.append(
                        {
                            "collection_name": collection_name,
                            "method": "semantic",
                            "query": query,
                            "query_vector": query_vector,
                            "top_k": top_k,
                            "score_threshold": score_threshold,
                            "filters": filters,
                        }
                    )
                tasks.append(
                    {
                        "collection_name": collection_name,
                        "method": "fulltext",
                        "query": query,
                        "query_vector": None,
                        "top_k": top_k,
                        "score_threshold": score_threshold,
                        "filters": filters,
                    }
                )
        return tasks

    def _execute_parallel(self, tasks: List[dict]) -> List[List[SearchResult]]:
        if not tasks:
            return []

        if len(tasks) == 1:
            return [self._execute_search(tasks[0])]

        result_lists = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._execute_search, task): task for task in tasks
            }
            for future in as_completed(futures):
                try:
                    results = future.result()
                    if results:
                        result_lists.append(results)
                except Exception:
                    pass

        return result_lists

    def _execute_search(self, task: dict) -> List[SearchResult]:
        return self.data_store.search(
            collection_name=task.get("collection_name", ""),
            query=task["query"],
            query_vector=task.get("query_vector"),
            top_k=task.get("top_k", 10),
            score_threshold=task.get("score_threshold", 0.0),
            filters=task.get("filters"),
            search_method=task["method"],
        )

    def _fuse_results(
        self, result_lists: List[List[SearchResult]]
    ) -> List[SearchResult]:
        fusion_mode = self.config.fusion_mode if self.config else FusionMode.RRF
        if fusion_mode == FusionMode.RRF or self.fusion_method == "rrf":
            return reciprocal_rank_fusion(result_lists)
        elif fusion_mode == FusionMode.WEIGHTED:
            return self._weighted_fusion(result_lists)
        else:
            return reciprocal_rank_fusion(result_lists)

    def _weighted_fusion(
        self, result_lists: List[List[SearchResult]]
    ) -> List[SearchResult]:
        weights = self.config.fusion_weights if self.config else None
        if not weights:
            return reciprocal_rank_fusion(result_lists)

        total_weight = sum(weights.values())
        if total_weight == 0:
            return reciprocal_rank_fusion(result_lists)

        scored_docs = {}
        for result_list in result_lists:
            if not result_list:
                continue
            method = "semantic"
            if result_list and result_list[0].retrieval_method:
                method = result_list[0].retrieval_method

            weight = (
                weights.get(method, 1.0 / len(weights))
                if weights
                else 1.0 / len(result_lists)
            )
            for rank, result in enumerate(result_list):
                key = result.doc_id or result.content
                if key not in scored_docs:
                    scored_docs[key] = {"result": result, "score": 0.0}
                scored_docs[key]["score"] += weight * (1.0 / (rank + 1))

        fused = []
        for key, data in scored_docs.items():
            result = data["result"]
            fused.append(
                SearchResult(
                    content=result.content,
                    score=data["score"] / total_weight,
                    doc_id=result.doc_id,
                    metadata={**result.metadata, "fusion_method": "weighted"},
                    retrieval_method="weighted_fusion",
                )
            )

        fused.sort(key=lambda x: x.score, reverse=True)
        return fused
