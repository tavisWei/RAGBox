"""Embedding response types and data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EmbeddingUsage:
    """Token usage information for embedding calls."""

    prompt_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: EmbeddingUsage) -> EmbeddingUsage:
        """Add two usage objects together."""
        return EmbeddingUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class EmbeddingResult:
    """Result from an embedding invocation."""

    embeddings: list[list[float]]
    model: str
    dimension: int
    usage: EmbeddingUsage = field(default_factory=EmbeddingUsage)

    @property
    def count(self) -> int:
        """Number of embeddings generated."""
        return len(self.embeddings)

    @property
    def is_empty(self) -> bool:
        """Check if no embeddings were generated."""
        return len(self.embeddings) == 0

    def get_embedding(self, index: int = 0) -> Optional[list[float]]:
        """Get embedding at specified index."""
        if 0 <= index < len(self.embeddings):
            return self.embeddings[index]
        return None
