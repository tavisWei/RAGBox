"""Base abstract classes for model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from api.core.model_providers.llm_types import LLMMessage, LLMResult, LLMUsage
from api.core.model_providers.embedding_types import EmbeddingResult


class BaseModelProvider(ABC):
    """Abstract base class for LLM model providers.

    All LLM providers (OpenAI, Anthropic, Ollama, etc.) must implement this interface.
    This provides a unified way to invoke different LLM backends.
    """

    @abstractmethod
    async def invoke(
        self,
        messages: list[LLMMessage],
        model_params: Optional[dict] = None,
    ) -> LLMResult:
        """Invoke the LLM with messages and optional parameters.

        Args:
            messages: List of conversation messages
            model_params: Optional model-specific parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResult with generated content and metadata

        Raises:
            ModelProviderError: If invocation fails
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        model_params: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """Stream LLM response chunks.

        Args:
            messages: List of conversation messages
            model_params: Optional model-specific parameters

        Yields:
            String chunks of the generated response

        Raises:
            ModelProviderError: If streaming fails
        """
        # Implementers should use: yield chunk
        # This is just a type hint for the return type
        if False:
            yield ""

    @abstractmethod
    async def get_model_list(self) -> list[str]:
        """Get list of available models for this provider.

        Returns:
            List of model names/identifiers
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of this provider.

        Returns:
            Provider name (e.g., "openai", "anthropic", "ollama")
        """
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider.

        Returns:
            Default model name
        """
        pass

    async def validate_model(self, model: str) -> bool:
        """Validate if a model is available.

        Args:
            model: Model name to validate

        Returns:
            True if model is available, False otherwise
        """
        available_models = await self.get_model_list()
        return model in available_models

    def get_default_params(self) -> dict:
        """Get default model parameters.

        Returns:
            Dictionary of default parameters
        """
        return {
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 1.0,
        }


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding model providers.

    All embedding providers (OpenAI, Cohere, HuggingFace, etc.) must implement this interface.
    This provides a unified way to generate embeddings from different backends.
    """

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            EmbeddingResult with embeddings and metadata

        Raises:
            EmbeddingProviderError: If embedding generation fails
        """
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query.

        This may use different embedding strategy than embed_texts for retrieval tasks.

        Args:
            query: Query string to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            EmbeddingProviderError: If embedding generation fails
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of this provider.

        Returns:
            Provider name (e.g., "openai", "cohere", "huggingface")
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            Dimension of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider.

        Returns:
            Default model name
        """
        pass

    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation: try to embed a test string
            result = await self.embed_texts(["test"])
            return not result.is_empty
        except Exception:
            return False

    def supports_batch(self) -> bool:
        """Check if provider supports batch embedding.

        Returns:
            True if batch embedding is supported
        """
        return True
