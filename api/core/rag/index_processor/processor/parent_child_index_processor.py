from enum import Enum
from typing import Any, List, Optional

from api.core.rag.cleaner.clean_processor import CleanProcessor
from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.index_processor.index_processor_base import BaseIndexProcessor
from api.core.rag.models.document import ChildDocument, Document
from api.core.rag.splitter.splitter_factory import SplitterFactory
from api.core.rag.splitter.splitter_types import SplitterConfig, SplitterType


class ParentChildMode(str, Enum):
    PARAGRAPH = "paragraph"
    FULL_DOC = "full-doc"


class ParentChildIndexProcessor(BaseIndexProcessor):
    def __init__(self, mode: ParentChildMode = ParentChildMode.PARAGRAPH, **kwargs):
        self.mode = mode
        self.parent_chunk_size = kwargs.get("parent_chunk_size", 2048)
        self.child_chunk_size = kwargs.get("child_chunk_size", 256)
        self.chunk_overlap = kwargs.get("chunk_overlap", 64)

    def extract(self, extract_setting: ExtractSetting, **kwargs) -> List[Document]:
        content = kwargs.get("content", "")
        if not content:
            return []
        return [Document(page_content=content)]

    def transform(self, documents: List[Document], **kwargs) -> List[Document]:
        process_rule = kwargs.get("process_rule")
        result = []

        parent_config = SplitterConfig(
            chunk_size=self.parent_chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        child_config = SplitterConfig(
            chunk_size=self.child_chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        parent_splitter = SplitterFactory.create(SplitterType.RECURSIVE, parent_config)
        child_splitter = SplitterFactory.create(SplitterType.RECURSIVE, child_config)

        for doc in documents:
            cleaned_text = CleanProcessor.clean(doc.page_content, process_rule)

            if self.mode == ParentChildMode.FULL_DOC:
                parent_chunks = [cleaned_text]
            else:
                parent_chunks = parent_splitter.split_text(cleaned_text)

            for parent_idx, parent_text in enumerate(parent_chunks):
                child_chunks = child_splitter.split_text(parent_text)
                children = [
                    ChildDocument(
                        page_content=chunk,
                        metadata={
                            "parent_index": parent_idx,
                            "child_index": i,
                            "total_children": len(child_chunks),
                        },
                    )
                    for i, chunk in enumerate(child_chunks)
                ]

                parent_doc = Document(
                    page_content=parent_text,
                    metadata={
                        **(doc.metadata or {}),
                        "parent_index": parent_idx,
                        "total_parents": len(parent_chunks),
                        "mode": self.mode.value,
                    },
                    children=children,
                )
                result.append(parent_doc)

        return result

    def load(self, dataset_id: str, documents: List[Document], **kwargs) -> None:
        pass

    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        pass

    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        return []
