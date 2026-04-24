from abc import ABC, abstractmethod
from typing import List
from api.core.rag.models.document import Document


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self) -> List[Document]:
        raise NotImplementedError
