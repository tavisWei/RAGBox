from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from api.core.rag.cleaner.clean_processor import CleanProcessor
from api.core.rag.extractor.entity.extract_setting import ExtractSetting
from api.core.rag.index_processor.index_processor_base import BaseIndexProcessor
from api.core.rag.models.document import ChildDocument, Document
from api.core.rag.splitter.splitter_factory import SplitterFactory
from api.core.rag.splitter.splitter_types import SplitterConfig, SplitterType


class ParentChildMode(str, Enum):
    PARAGRAPH = "paragraph"
    FULL_DOC = "full-doc"


def flatten_parent_child(documents: List[Document]) -> List[Document]:
    """Flatten parent documents into storable child documents.

    Each child carries parent_id / parent_content in its metadata so a child
    hit can be mapped back to the parent passage at retrieval time.
    """
    flattened: List[Document] = []
    for parent in documents:
        if not parent.children:
            # Already a flat (child) document — pass through unchanged.
            flattened.append(parent)
            continue
        parent_meta = parent.metadata or {}
        parent_id = parent_meta.get("doc_id") or str(uuid4())
        for child in parent.children or []:
            flattened.append(
                Document(
                    page_content=child.page_content,
                    metadata={
                        **parent_meta,
                        **(child.metadata or {}),
                        "parent_id": parent_id,
                        "parent_content": parent.page_content,
                        "index_mode": "parent_child",
                    },
                )
            )
    return flattened


def collapse_parent_child_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map child-chunk hits back to their parent passage.

    Input is score-ordered retrieval dicts; children sharing a parent_id are
    deduplicated to the best-scoring child, with content replaced by the
    parent passage. Docs without parent metadata pass through unchanged.
    """
    collapsed: List[Dict[str, Any]] = []
    seen_parents = set()
    for doc in docs:
        metadata = doc.get("metadata") or {}
        parent_id = metadata.get("parent_id")
        if not parent_id:
            collapsed.append(doc)
            continue
        if parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)
        collapsed.append(
            {**doc, "content": metadata.get("parent_content") or doc.get("content")}
        )
    return collapsed


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
        data_store = kwargs.get("data_store")
        if data_store is None:
            raise ValueError("load requires a data_store")
        # Embeddings are computed over the flattened children by the caller.
        self._load_to_store(
            dataset_id,
            flatten_parent_child(documents),
            data_store,
            kwargs.get("embeddings"),
        )

    def clean(
        self, dataset_id: str, node_ids: Optional[List[str]] = None, **kwargs
    ) -> None:
        data_store = kwargs.get("data_store")
        if data_store is None:
            raise ValueError("clean requires a data_store")
        self._clean_from_store(dataset_id, data_store, node_ids)

    def retrieve(
        self, query: str, dataset_id: str, top_k: int, **kwargs
    ) -> List[Document]:
        data_store = kwargs.get("data_store")
        if data_store is None:
            raise ValueError("retrieve requires a data_store")
        children = self._retrieve_from_store(
            query,
            dataset_id,
            top_k,
            data_store,
            query_vector=kwargs.get("query_vector"),
            search_method=kwargs.get("search_method", "hybrid"),
        )
        collapsed = collapse_parent_child_docs(
            [
                {"content": doc.page_content, "metadata": doc.metadata or {}}
                for doc in children
            ]
        )
        return [
            Document(page_content=doc["content"], metadata=doc["metadata"])
            for doc in collapsed
        ]
