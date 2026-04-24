from abc import ABC, abstractmethod
from typing import List, Dict, Any

from api.core.rag.splitter.splitter_types import SplitterConfig


class BaseTextSplitter(ABC):
    def __init__(self, config: SplitterConfig):
        if config.chunk_overlap > config.chunk_size:
            raise ValueError(
                f"chunk_overlap ({config.chunk_overlap}) must be <= chunk_size ({config.chunk_size})"
            )
        self.config = config

    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        pass

    def split_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for doc in documents:
            text = doc.get("content", "")
            metadata = doc.get("metadata", {})
            chunks = self.split_text(text)
            for i, chunk in enumerate(chunks):
                chunk_doc = {
                    "content": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    },
                }
                result.append(chunk_doc)
        return result

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "BaseTextSplitter":
        return cls(config)
