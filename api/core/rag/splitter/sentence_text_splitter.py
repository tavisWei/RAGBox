from typing import List, Optional
from .base_splitter import BaseTextSplitter
from .splitter_types import SplitterConfig


class SentenceTextSplitter(BaseTextSplitter):
    def __init__(self, config: Optional[SplitterConfig] = None, **kwargs):
        if config is None:
            config = SplitterConfig(**kwargs)
        super().__init__(config)

        try:
            import nltk

            nltk.data.find("tokenizers/punkt")
        except LookupError:
            import nltk

            nltk.download("punkt", quiet=True)

        self._nltk = __import__("nltk")

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        try:
            sentences = self._nltk.sent_tokenize(text)
        except Exception:
            sentences = self._fallback_split(text)

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sent_length = len(sentence)

            if current_length + sent_length <= self.config.chunk_size:
                current_chunk.append(sentence)
                current_length += sent_length + 1
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = sent_length

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _fallback_split(self, text: str) -> List[str]:
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "SentenceTextSplitter":
        return cls(config=config)
