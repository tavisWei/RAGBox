"""Abstract base class for model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from api.core.model_providers.entities.provider_entities import (
    EmbeddingResult,
    LLMResult,
    ModelConfig,
    ModelType,
    ProviderConfig,
    RerankResult,
)

if TYPE_CHECKING:
    from api.core.model_providers.model_instance import ModelInstance


class BaseProvider(ABC):
    """Abstract base class for all model providers.

    All model providers (OpenAI, Anthropic, Ollama, etc.) must implement
    this interface to provide unified LLM, embedding, and rerank capabilities.
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._models_cache: Optional[Dict[str, ModelConfig]] = None

    @abstractmethod
    async def invoke_llm(
        self,
        model: ModelConfig,
        prompt: str,
        **kwargs: Any,
    ) -> LLMResult:
        """Invoke LLM with a prompt and return the result.

        Args:
            model: Model configuration
            prompt: Input prompt text
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResult with generated content and metadata
        """
        pass

    @abstractmethod
    async def stream_llm(
        self,
        model: ModelConfig,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response tokens.

        Args:
            model: Model configuration
            prompt: Input prompt text
            **kwargs: Additional provider-specific parameters

        Yields:
            String tokens from the LLM response
        """
        if False:
            yield ""

    @abstractmethod
    async def invoke_embedding(
        self,
        model: ModelConfig,
        texts: List[str],
        **kwargs: Any,
    ) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            model: Model configuration
            texts: List of text strings to embed
            **kwargs: Additional provider-specific parameters

        Returns:
            EmbeddingResult with embedding vectors and metadata
        """
        pass

    async def invoke_rerank(
        self,
        model: ModelConfig,
        query: str,
        documents: List[str],
        **kwargs: Any,
    ) -> RerankResult:
        """Rerank documents based on relevance to query.

        Args:
            model: Model configuration
            query: Query string
            documents: List of documents to rerank
            **kwargs: Additional provider-specific parameters

        Returns:
            RerankResult with reranked documents and scores
        """
        raise NotImplementedError("Rerank not supported by this provider")

    @abstractmethod
    def list_models(self, model_type: Optional[ModelType] = None) -> List[str]:
        """List available models for this provider.

        Args:
            model_type: Optional filter by model type

        Returns:
            List of model names/identifiers
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate provider credentials.

        Returns:
            True if credentials are valid, False otherwise
        """
        pass

    def get_model_instance(
        self,
        model_name: str,
        model_type: ModelType,
    ) -> ModelInstance:
        """Get a model instance wrapper for a specific model.

        Args:
            model_name: Name of the model
            model_type: Type of the model (LLM, embedding, rerank)

        Returns:
            ModelInstance wrapper for the specified model
        """
        from api.core.model_providers.model_instance import ModelInstance

        return ModelInstance(
            provider=self,
            model_name=model_name,
            model_type=model_type,
        )

    def get_model_config(
        self,
        model_name: str,
        model_type: ModelType,
    ) -> ModelConfig:
        """Get model configuration for a specific model.

        Args:
            model_name: Name of the model
            model_type: Type of the model

        Returns:
            ModelConfig for the specified model
        """
        return ModelConfig(
            model_name=model_name,
            model_type=model_type,
            provider=self.config.provider_name,
        )

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.config.provider_name

    @property
    def provider_type(self) -> str:
        """Get the provider type."""
        return self.config.provider_type.value

    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            return self.validate_credentials()
        except Exception:
            return False

    def supports_model_type(self, model_type: ModelType) -> bool:
        """Check if provider supports a specific model type.

        Args:
            model_type: Model type to check

        Returns:
            True if supported, False otherwise
        """
        models = self.list_models(model_type)
        return len(models) > 0


__all__ = ["BaseProvider"]
