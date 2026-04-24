from abc import ABC, abstractmethod
from typing import List, Optional
from api.core.rag.models.document import Document


class BaseRerankRunner(ABC):
    @abstractmethod
    def run(
        self,
        query: str,
        documents: List[Document],
        score_threshold: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> List[Document]:
        raise NotImplementedError
