from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from .base_splitter import BaseTextSplitter
from .splitter_types import SplitterConfig


@dataclass
class ParentChildChunk:
    parent_content: str
    parent_metadata: Dict[str, Any]
    child_chunks: List[str]
    child_metadata: List[Dict[str, Any]]


class ParentChildTextSplitter(BaseTextSplitter):
    def __init__(
        self,
        config: Optional[SplitterConfig] = None,
        parent_chunk_size: int = 2048,
        child_chunk_size: int = 256,
        **kwargs,
    ):
        if config is None:
            config = SplitterConfig(**kwargs)
        super().__init__(config)

        self._parent_chunk_size = parent_chunk_size or config.parent_chunk_size
        self._child_chunk_size = child_chunk_size or config.child_chunk_size

    def split_text(self, text: str) -> List[str]:
        result = self.split_with_parents(text)
        return result.child_chunks

    def split_with_parents(self, text: str) -> ParentChildChunk:
        if not text:
            return ParentChildChunk("", {}, [], [])

        parent_chunks = self._split_by_size(
            text, self._parent_chunk_size, self.config.chunk_overlap
        )

        all_child_chunks = []
        all_child_metadata = []

        for parent_idx, parent_content in enumerate(parent_chunks):
            child_chunks = self._split_by_size(
                parent_content, self._child_chunk_size, self.config.chunk_overlap // 2
            )

            for child_idx, child_content in enumerate(child_chunks):
                all_child_chunks.append(child_content)
                all_child_metadata.append(
                    {
                        "parent_index": parent_idx,
                        "child_index": child_idx,
                        "parent_content": parent_content,
                    }
                )

        return ParentChildChunk(
            parent_content=text,
            parent_metadata={"total_parents": len(parent_chunks)},
            child_chunks=all_child_chunks,
            child_metadata=all_child_metadata,
        )

    def _split_by_size(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text[start:end].rfind(" ")
                if boundary > chunk_size // 2:
                    end = start + boundary

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            next_start = end - overlap
            if next_start <= start:
                next_start = end
            start = next_start

        return chunks

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "ParentChildTextSplitter":
        return cls(
            config=config,
            parent_chunk_size=config.parent_chunk_size,
            child_chunk_size=config.child_chunk_size,
        )
