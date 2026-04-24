from typing import List, Optional, Callable
import numpy as np
from .base_splitter import BaseTextSplitter
from .splitter_types import SplitterConfig


class SemanticTextSplitter(BaseTextSplitter):
    def __init__(
        self,
        config: Optional[SplitterConfig] = None,
        embedding_function: Optional[Callable[[str], List[float]]] = None,
        breakpoint_threshold: float = 0.5,
        **kwargs,
    ):
        if config is None:
            config = SplitterConfig(**kwargs)
        super().__init__(config)

        self._embedding_function = embedding_function
        self._breakpoint_threshold = breakpoint_threshold

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        if not self._embedding_function:
            from .sentence_text_splitter import SentenceTextSplitter

            fallback = SentenceTextSplitter(self.config)
            return fallback.split_text(text)

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return sentences

        embeddings = [self._embedding_function(sent) for sent in sentences]

        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        breakpoints = []
        for i, sim in enumerate(similarities):
            if sim < self._breakpoint_threshold:
                breakpoints.append(i + 1)

        chunks = []
        start = 0
        for bp in breakpoints:
            chunk = " ".join(sentences[start:bp])
            if len(chunk) <= self.config.chunk_size:
                chunks.append(chunk)
            else:
                chunks.extend(self._split_by_size(chunk))
            start = bp

        if start < len(sentences):
            chunks.append(" ".join(sentences[start:]))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        a = np.array(vec1)
        b = np.array(vec2)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _split_by_size(self, text: str) -> List[str]:
        chunks = []
        for i in range(0, len(text), self.config.chunk_size):
            chunks.append(text[i : i + self.config.chunk_size])
        return chunks

    @classmethod
    def from_config(cls, config: SplitterConfig) -> "SemanticTextSplitter":
        return cls(config=config)
