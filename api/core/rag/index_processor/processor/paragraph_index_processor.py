from typing import Any, List, Optional

from api.core.rag.cleaner.clean_processor import CleanProcessor
from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.index_processor.index_processor_base import BaseIndexProcessor
from api.core.rag.models.document import Document
from api.core.rag.splitter.splitter_factory import SplitterFactory
from api.core.rag.splitter.splitter_types import SplitterConfig, SplitterType


class ParagraphIndexProcessor(BaseIndexProcessor):
    def extract(self, extract_setting: ExtractSetting, **kwargs) -> List[Document]:
        content = kwargs.get("content", "")
        if not content:
            return []
        return [Document(page_content=content)]

    def transform(self, documents: List[Document], **kwargs) -> List[Document]:
        process_rule = kwargs.get("process_rule")
        splitter_type = kwargs.get("splitter_type", SplitterType.RECURSIVE)
        config = kwargs.get("config")

        if config is None:
            config = SplitterConfig(
                chunk_size=kwargs.get("chunk_size", 512),
                chunk_overlap=kwargs.get("chunk_overlap", 64),
            )

        splitter = SplitterFactory.create(splitter_type, config)
        result = []

        for doc in documents:
            cleaned_text = CleanProcessor.clean(doc.page_content, process_rule)
            chunks = splitter.split_text(cleaned_text)
            for i, chunk in enumerate(chunks):
                chunk_doc = Document(
                    page_content=chunk,
                    metadata={
                        **(doc.metadata or {}),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "source": doc.metadata.get("source", "")
                        if doc.metadata
                        else "",
                    },
                )
                result.append(chunk_doc)

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
        return [Document(page_content=content)]

    def transform(self, documents: List[Document], **kwargs) -> List[Document]:
        """
        Transform documents by cleaning and splitting them into chunks.
        """
        process_rule = kwargs.get("process_rule")
        splitter_type = kwargs.get("splitter_type", SplitterType.RECURSIVE)
        config = kwargs.get("config")

        if config is None:
            config = SplitterConfig(
                chunk_size=kwargs.get("chunk_size", 512),
                chunk_overlap=kwargs.get("chunk_overlap", 64),
            )

        splitter = SplitterFactory.create(splitter_type, config)
        result = []

        for doc in documents:
            # Clean the text
            cleaned_text = CleanProcessor.clean(doc.page_content, process_rule)
            # Split into chunks
            chunks = splitter.split_text(cleaned_text)
            for i, chunk in enumerate(chunks):
                chunk_doc = Document(
                    page_content=chunk,
                    metadata={
                        **(doc.metadata or {}),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "source": doc.metadata.get("source", "")
                        if doc.metadata
                        else "",
                    },
                )
                result.append(chunk_doc)

        return result

    def load(self, dataset_id: str, documents: List[Document], **kwargs) -> None:
        """
        Load documents into the vector store for a dataset.
        Placeholder: actual implementation would persist to a vector database.
        """
        # Placeholder for vector store insertion
        pass

    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        """
        Clean/remove documents from the vector store.
        Placeholder: actual implementation would delete from a vector database.
        """
        # Placeholder for vector store deletion
        pass

    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        """
        Retrieve relevant documents from the vector store.
        Placeholder: actual implementation would query a vector database.
        """
        # Placeholder for vector store retrieval
        return []
