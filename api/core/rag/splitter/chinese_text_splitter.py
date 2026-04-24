import re
from typing import Any, List, Optional

from api.core.rag.splitter.base_splitter import BaseTextSplitter
from api.core.rag.splitter.chinese_separators import CHINESE_SEPARATORS
from api.core.rag.splitter.splitter_types import SplitterConfig


class ChineseTextSplitter(BaseTextSplitter):
    def __init__(
        self,
        config: Optional[SplitterConfig] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
        **kwargs: Any,
    ):
        if config is None:
            config = SplitterConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=separators if separators is not None else CHINESE_SEPARATORS,
                keep_separator=keep_separator,
                **kwargs,
            )
        super().__init__(config)
        self._chunk_size = config.chunk_size
        self._chunk_overlap = config.chunk_overlap
        self._separators = (
            config.separators if config.separators is not None else CHINESE_SEPARATORS
        )
        self._keep_separator = config.keep_separator
        self._length_function = lambda x: [len(t) for t in x]

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "ChineseTextSplitter":
        return cls(config=config)

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        return self._split_text(text, self._separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        final_chunks: List[str] = []
        separator = separators[-1]
        new_separators: List[str] = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1 :]
                break

        splits = self._split_text_with_regex(text, separator, self._keep_separator)
        good_splits: List[str] = []
        good_splits_lengths: List[int] = []
        separator_for_merge = "" if self._keep_separator else separator
        splits_lengths = self._length_function(splits)

        for split, split_len in zip(splits, splits_lengths):
            if split_len < self.config.chunk_size:
                good_splits.append(split)
                good_splits_lengths.append(split_len)
            else:
                if good_splits:
                    merged = self._merge_splits(
                        good_splits, separator_for_merge, good_splits_lengths
                    )
                    final_chunks.extend(merged)
                    good_splits = []
                    good_splits_lengths = []
                if not new_separators:
                    final_chunks.append(split)
                else:
                    other_chunks = self._split_text(split, new_separators)
                    final_chunks.extend(other_chunks)

        if good_splits:
            merged = self._merge_splits(
                good_splits, separator_for_merge, good_splits_lengths
            )
            final_chunks.extend(merged)

        return final_chunks

    def _split_text_with_regex(
        self, text: str, separator: str, keep_separator: bool
    ) -> List[str]:
        if separator:
            if keep_separator:
                parts = re.split(f"({re.escape(separator)})", text)
                splits = []
                for i in range(1, len(parts), 2):
                    splits.append(parts[i - 1] + parts[i])
                if len(parts) % 2 != 0:
                    splits.append(parts[-1])
            else:
                splits = text.split(separator)
        else:
            splits = list(text)

        return [s for s in splits if s not in {"", "\n"}]

    def _merge_splits(
        self, splits: List[str], separator: str, lengths: List[int]
    ) -> List[str]:
        separator_len = len(separator) if separator else 0
        docs: List[str] = []
        current_doc: List[str] = []
        current_lengths: List[int] = []
        total = 0

        for split, split_len in zip(splits, lengths):
            added_len = split_len + (separator_len if current_doc else 0)

            if total + added_len > self.config.chunk_size:
                if current_doc:
                    doc = separator.join(current_doc)
                    if doc:
                        docs.append(doc)

                    while current_doc and (
                        total > self.config.chunk_overlap
                        or (total + added_len > self.config.chunk_size and total > 0)
                    ):
                        total -= current_lengths[0]
                        total -= separator_len if len(current_doc) > 1 else 0
                        current_doc = current_doc[1:]
                        current_lengths = current_lengths[1:]

            current_doc.append(split)
            current_lengths.append(split_len)
            total += split_len + (separator_len if len(current_doc) > 1 else 0)

        if current_doc:
            doc = separator.join(current_doc)
            if doc:
                docs.append(doc)

        return docs
