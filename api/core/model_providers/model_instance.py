"""Model instance wrapper for provider delegation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, List, Optional

from api.core.model_providers.entities.provider_entities import (
    EmbeddingResult,
    LLMResult,
    ModelConfig,
    ModelType,
    RerankResult,
)

if TYPE_CHECKING:
    from api.core.model_providers.base_provider import BaseProvider


class ModelInstance:
    """Wrapper for a specific model instance.

    Provides a convenient interface for invoking a specific model,
    delegating all calls to the underlying provider.
    """

    def __init__(
        self,
        provider: BaseProvider,
        model_name: str,
        model_type: ModelType,
    ) -> None:
        self._provider = provider
        self._model_name = model_name
        self._model_type = model_type
        self._model_config: Optional[ModelConfig] = None

    @property
    def provider(self) -> BaseProvider:
        """Get the underlying provider."""
        return self._provider

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name

    @property
    def model_type(self) -> ModelType:
        """Get the model type."""
        return self._model_type

    @property
    def model_config(self) -> ModelConfig:
        """Get or create the model configuration."""
        if self._model_config is None:
            self._model_config = ModelConfig(
                model_name=self._model_name,
                model_type=self._model_type,
                provider=self._provider.config.provider_name,
            )
        return self._model_config

    async def invoke(self, prompt: str, **kwargs: Any) -> LLMResult:
        """Invoke LLM with a prompt.

        Args:
            prompt: Input prompt text
            **kwargs: Additional parameters passed to provider

        Returns:
            LLMResult with generated content

        Raises:
            ValueError: If model is not an LLM
        """
        if self._model_type != ModelType.LLM:
            raise ValueError(
                f"Model '{self._model_name}' is not an LLM model. "
                f"Current type: {self._model_type.value}"
            )
        return await self._provider.invoke_llm(self.model_config, prompt, **kwargs)

    async def stream(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response tokens.

        Args:
            prompt: Input prompt text
            **kwargs: Additional parameters passed to provider

        Yields:
            String tokens from the LLM response

        Raises:
            ValueError: If model is not an LLM
        """
        if self._model_type != ModelType.LLM:
            raise ValueError(
                f"Model '{self._model_name}' is not an LLM model. "
                f"Current type: {self._model_type.value}"
            )
        async for token in self._provider.stream_llm(
            self.model_config, prompt, **kwargs
        ):
            yield token

    async def embed(self, texts: List[str], **kwargs: Any) -> EmbeddingResult:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed
            **kwargs: Additional parameters passed to provider

        Returns:
            EmbeddingResult with embedding vectors

        Raises:
            ValueError: If model is not an embedding model
        """
        if self._model_type != ModelType.EMBEDDING:
            raise ValueError(
                f"Model '{self._model_name}' is not an embedding model. "
                f"Current type: {self._model_type.value}"
            )
        return await self._provider.invoke_embedding(self.model_config, texts, **kwargs)

    async def rerank(
        self,
        query: str,
        documents: List[str],
        **kwargs: Any,
    ) -> RerankResult:
        """Rerank documents based on query relevance.

        Args:
            query: Query string
            documents: List of documents to rerank
            **kwargs: Additional parameters passed to provider

        Returns:
            RerankResult with reranked documents and scores

        Raises:
            ValueError: If model is not a rerank model
        """
        if self._model_type != ModelType.RERANK:
            raise ValueError(
                f"Model '{self._model_name}' is not a rerank model. "
                f"Current type: {self._model_type.value}"
            )
        return await self._provider.invoke_rerank(
            self.model_config, query, documents, **kwargs
        )

    def __repr__(self) -> str:
        return (
            f"ModelInstance("
            f"provider='{self._provider.config.provider_name}', "
            f"model='{self._model_name}', "
            f"type={self._model_type.value})"
        )


__all__ = ["ModelInstance"]
