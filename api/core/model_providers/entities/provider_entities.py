"""Model provider entities and configuration classes."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Type of model."""

    LLM = "llm"
    EMBEDDING = "embedding"
    RERANK = "rerank"


class ProviderType(str, Enum):
    """Type of provider."""

    BUILTIN = "builtin"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """Provider configuration for initialization."""

    provider_name: str = Field(..., description="Unique provider identifier")
    provider_type: ProviderType = Field(
        default=ProviderType.BUILTIN, description="Provider type (builtin or custom)"
    )
    api_key: Optional[str] = Field(
        default=None, description="API key for authentication"
    )
    api_base: Optional[str] = Field(
        default=None, description="Base URL for API requests"
    )
    credentials: Dict[str, Any] = Field(
        default_factory=dict, description="Additional credentials and configuration"
    )

    class Config:
        extra = "allow"


class ModelConfig(BaseModel):
    """Model configuration for invocation."""

    model_name: str = Field(..., description="Model identifier")
    model_type: ModelType = Field(..., description="Type of model")
    provider: str = Field(..., description="Provider name")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Model-specific parameters"
    )
    max_tokens: int = Field(default=4096, description="Maximum tokens for generation")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )

    class Config:
        extra = "allow"


class LLMResult(BaseModel):
    """Result from LLM invocation."""

    content: str = Field(..., description="Generated text content")
    usage: Dict[str, int] = Field(
        default_factory=dict, description="Token usage information"
    )
    finish_reason: Optional[str] = Field(
        default=None, description="Reason for completion"
    )
    model: Optional[str] = Field(default=None, description="Model used for generation")

    @property
    def is_complete(self) -> bool:
        """Check if response completed successfully."""
        return self.finish_reason in (None, "stop")

    @property
    def is_truncated(self) -> bool:
        """Check if response was truncated."""
        return self.finish_reason == "length"


class EmbeddingResult(BaseModel):
    """Result from embedding invocation."""

    embeddings: List[List[float]] = Field(
        default_factory=list, description="List of embedding vectors"
    )
    usage: Dict[str, int] = Field(
        default_factory=dict, description="Token usage information"
    )
    model: Optional[str] = Field(default=None, description="Model used for embedding")

    @property
    def count(self) -> int:
        """Number of embeddings generated."""
        return len(self.embeddings)

    @property
    def is_empty(self) -> bool:
        """Check if no embeddings were generated."""
        return len(self.embeddings) == 0

    @property
    def dimension(self) -> Optional[int]:
        """Get embedding dimension."""
        if self.embeddings:
            return len(self.embeddings[0])
        return None


class RerankResult(BaseModel):
    """Result from reranking invocation."""

    results: List[Dict[str, Any]] = Field(
        default_factory=list, description="Reranked results with scores"
    )
    usage: Dict[str, int] = Field(
        default_factory=dict, description="Token usage information"
    )
    model: Optional[str] = Field(default=None, description="Model used for reranking")

    @property
    def count(self) -> int:
        """Number of reranked results."""
        return len(self.results)


__all__ = [
    "ModelType",
    "ProviderType",
    "ProviderConfig",
    "ModelConfig",
    "LLMResult",
    "EmbeddingResult",
    "RerankResult",
]
