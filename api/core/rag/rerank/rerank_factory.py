from api.core.rag.rerank.rerank_base import BaseRerankRunner
from api.core.rag.rerank.rerank_type import RerankMode


class RerankRunnerFactory:
    @staticmethod
    def create_rerank_runner(runner_type: str, *args, **kwargs) -> BaseRerankRunner:
        if runner_type == RerankMode.RERANKING_MODEL:
            from api.core.rag.rerank.rerank_model import RerankModelRunner

            return RerankModelRunner(*args, **kwargs)
        elif runner_type == RerankMode.WEIGHTED_SCORE:
            from api.core.rag.rerank.weight_rerank import WeightRerankRunner

            return WeightRerankRunner(*args, **kwargs)
        else:
            raise ValueError(f"Unknown runner type: {runner_type}")
