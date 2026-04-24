from abc import ABC, abstractmethod
from typing import Any, List, Optional
from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.models.document import AttachmentDocument, Document
from api.core.rag.index_processor.constant.index_type import IndexTechniqueType


class BaseIndexProcessor(ABC):
    @abstractmethod
    def extract(self, extract_setting: ExtractSetting, **kwargs) -> List[Document]:
        raise NotImplementedError

    @abstractmethod
    def transform(self, documents: List[Document], **kwargs) -> List[Document]:
        raise NotImplementedError

    @abstractmethod
    def load(self, dataset_id: str, documents: List[Document], **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        raise NotImplementedError
