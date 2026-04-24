from typing import List, Optional
from .base_splitter import BaseTextSplitter
from .splitter_types import SplitterConfig


class TokenTextSplitter(BaseTextSplitter):
    def __init__(self, config: Optional[SplitterConfig] = None, **kwargs):
        if config is None:
            config = SplitterConfig(**kwargs)
        super().__init__(config)

        try:
            import tiktoken

            self._tiktoken = tiktoken
        except ImportError:
            self._tiktoken = None

        model_name = self.config.model_name or "gpt-3.5-turbo"
        if self._tiktoken:
            try:
                self._encoding = self._tiktoken.encoding_for_model(model_name)
            except KeyError:
                self._encoding = self._tiktoken.get_encoding("cl100k_base")
        else:
            self._encoding = None

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        if self._encoding is None:
            # Fallback to character-based splitting when tiktoken is not available
            return self._fallback_split(text)

        tokens = self._encoding.encode(text)
        chunks = []
        start = 0

        while start < len(tokens):
            end = min(start + self.config.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self._encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            if end >= len(tokens):
                break
            start = end - self.config.chunk_overlap

        return chunks

    def _fallback_split(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.config.chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            if end >= len(text):
                break
            start = end - self.config.chunk_overlap
        return chunks

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "TokenTextSplitter":
        return cls(config=config)
