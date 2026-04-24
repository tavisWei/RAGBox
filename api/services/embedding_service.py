"""Embedding service with support for OpenAI, Ollama, and HuggingFace models."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

from api.services.resource_config_service import ResourceConfigService, ResourceLevel


class EmbeddingError(Exception):
    """Base exception for embedding errors."""

    pass


class ModelNotFoundError(EmbeddingError):
    """Raised when the specified embedding model is not found."""

    pass


class EmbeddingProviderError(EmbeddingError):
    """Raised when the embedding provider encounters an error."""

    pass


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""

    provider: EmbeddingProvider
    model_name: str
    dimension: Optional[int] = None
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0

    # Provider-specific settings
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    ollama_host: str = "http://localhost:11434"
    huggingface_device: str = "cpu"


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    embeddings: List[List[float]]
    model: str
    dimension: int
    total_tokens: Optional[int] = None
    usage: Optional[Dict[str, int]] = None


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts."""
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        pass

    def _get_dimension(self, sample_embedding: List[float]) -> int:
        """Get embedding dimension from a sample."""
        return len(sample_embedding)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider supporting text-embedding-3-small and text-embedding-3-large."""

    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = config.api_base or os.getenv(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )

        if not self.api_key:
            raise EmbeddingError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable."
            )

    async def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts using OpenAI API."""
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=self.config.model_name,
                dimension=self.MODEL_DIMENSIONS.get(self.config.model_name, 1536),
            )

        # Process in batches
        all_embeddings = []
        total_tokens = 0

        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i : i + self.config.batch_size]
            batch_result = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(batch_result["embeddings"])
            total_tokens += batch_result.get("total_tokens", 0)

        dimension = self._get_dimension(all_embeddings[0]) if all_embeddings else 1536

        return EmbeddingResult(
            embeddings=all_embeddings,
            model=self.config.model_name,
            dimension=dimension,
            total_tokens=total_tokens,
            usage={"total_tokens": total_tokens},
        )

    async def _embed_batch_with_retry(self, texts: List[str]) -> Dict[str, Any]:
        """Embed a batch of texts with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                return await self._embed_batch(texts)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (
                        2**attempt
                    )  # Exponential backoff
                    await asyncio.sleep(delay)

        raise EmbeddingProviderError(
            f"Failed to embed batch after {self.config.max_retries} retries: {last_error}"
        )

    async def _embed_batch(self, texts: List[str]) -> Dict[str, Any]:
        """Embed a batch of texts using OpenAI API."""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.api_base}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model_name,
                    "input": texts,
                },
            )

            if response.status_code == 401:
                raise EmbeddingError("Invalid OpenAI API key")
            elif response.status_code == 404:
                raise ModelNotFoundError(f"Model {self.config.model_name} not found")
            elif response.status_code != 200:
                raise EmbeddingProviderError(
                    f"OpenAI API error: {response.status_code} - {response.text}"
                )

            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            total_tokens = data.get("usage", {}).get("total_tokens", 0)

            return {
                "embeddings": embeddings,
                "total_tokens": total_tokens,
            }

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        result = await self.embed_texts([text])
        return result.embeddings[0]

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.api_base}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception:
            return False


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Ollama embedding provider for local models."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.ollama_host = config.ollama_host or os.getenv(
            "OLLAMA_HOST", "http://localhost:11434"
        )

    async def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts using Ollama API."""
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=self.config.model_name,
                dimension=768,  # Default dimension
            )

        # Process in batches
        all_embeddings = []

        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i : i + self.config.batch_size]
            batch_embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(batch_embeddings)

        dimension = self._get_dimension(all_embeddings[0]) if all_embeddings else 768

        return EmbeddingResult(
            embeddings=all_embeddings,
            model=self.config.model_name,
            dimension=dimension,
        )

    async def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                return await self._embed_batch(texts)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        raise EmbeddingProviderError(
            f"Failed to embed batch after {self.config.max_retries} retries: {last_error}"
        )

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts using Ollama API."""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.ollama_host}/api/embed",
                json={
                    "model": self.config.model_name,
                    "input": texts,
                },
            )

            if response.status_code == 404:
                raise ModelNotFoundError(
                    f"Model {self.config.model_name} not found in Ollama"
                )
            elif response.status_code != 200:
                raise EmbeddingProviderError(
                    f"Ollama API error: {response.status_code} - {response.text}"
                )

            data = response.json()
            return data["embeddings"]

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        result = await self.embed_texts([text])
        return result.embeddings[0]

    async def health_check(self) -> bool:
        """Check if Ollama server is accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_host}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """HuggingFace transformers embedding provider for local models."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.device = config.huggingface_device
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """Lazy load the model and tokenizer."""
        if self._model is None:
            try:
                from transformers import AutoModel, AutoTokenizer
                import torch

                self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
                self._model = AutoModel.from_pretrained(self.config.model_name)
                self._model.to(self.device)
                self._model.eval()
            except ImportError:
                raise EmbeddingError(
                    "HuggingFace transformers not installed. "
                    "Install with: pip install transformers torch"
                )
            except Exception as e:
                raise ModelNotFoundError(
                    f"Failed to load model {self.config.model_name}: {e}"
                )

    async def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts using HuggingFace transformers."""
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=self.config.model_name,
                dimension=768,
            )

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self._embed_texts_sync, texts)

        dimension = self._get_dimension(embeddings[0]) if embeddings else 768

        return EmbeddingResult(
            embeddings=embeddings,
            model=self.config.model_name,
            dimension=dimension,
        )

    def _embed_texts_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous embedding generation (runs in thread pool)."""
        self._load_model()

        try:
            import torch
        except ImportError:
            raise EmbeddingError(
                "PyTorch not installed. Install with: pip install torch"
            )

        all_embeddings = []

        with torch.no_grad():
            for i in range(0, len(texts), self.config.batch_size):
                batch = texts[i : i + self.config.batch_size]

                # Tokenize
                encoded = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                encoded = {k: v.to(self.device) for k, v in encoded.items()}

                # Get embeddings
                outputs = self._model(**encoded)

                # Use mean pooling
                attention_mask = encoded["attention_mask"]
                embeddings = self._mean_pooling(
                    outputs.last_hidden_state, attention_mask
                )

                # Normalize embeddings
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

                all_embeddings.extend(embeddings.cpu().numpy().tolist())

        return all_embeddings

    def _mean_pooling(self, token_embeddings, attention_mask):
        """Apply mean pooling to get sentence embeddings."""
        try:
            import torch
        except ImportError:
            raise EmbeddingError("PyTorch not installed")

        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        )
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
            input_mask_expanded.sum(1), min=1e-9
        )

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        result = await self.embed_texts([text])
        return result.embeddings[0]

    async def health_check(self) -> bool:
        """Check if the model can be loaded."""
        try:
            self._load_model()
            return True
        except Exception:
            return False


class DemoEmbeddingProvider(BaseEmbeddingProvider):
    """Demo embedding provider that returns mock embeddings."""

    async def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """Generate mock embeddings for demonstration."""
        import random

        dimension = 1536
        embeddings = []
        for _ in texts:
            embedding = [random.uniform(-1, 1) for _ in range(dimension)]
            norm = sum(x**2 for x in embedding) ** 0.5
            embedding = [x / norm for x in embedding]
            embeddings.append(embedding)

        return EmbeddingResult(
            embeddings=embeddings,
            model="demo",
            dimension=dimension,
            total_tokens=sum(len(t) for t in texts),
            usage={"prompt_tokens": sum(len(t) for t in texts)},
        )

    async def embed_single(self, text: str) -> List[float]:
        """Generate mock embedding for a single text."""
        result = await self.embed_texts([text])
        return result.embeddings[0]

    async def health_check(self) -> bool:
        """Demo provider is always available."""
        return True


class EmbeddingService:
    """
    Main embedding service with configuration-driven model selection.

    Supports:
    - OpenAI text-embedding-3-small and text-embedding-3-large
    - Ollama local models
    - HuggingFace transformers models
    """

    # Default models for each resource level
    DEFAULT_MODELS = {
        ResourceLevel.LOW: {
            "provider": EmbeddingProvider.OLLAMA,
            "model": "nomic-embed-text",
        },
        ResourceLevel.MEDIUM: {
            "provider": EmbeddingProvider.OPENAI,
            "model": "text-embedding-3-small",
        },
        ResourceLevel.HIGH: {
            "provider": EmbeddingProvider.OPENAI,
            "model": "text-embedding-3-large",
        },
    }

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize embedding service with optional config."""
        self.config = config
        self._provider: Optional[BaseEmbeddingProvider] = None

    def get_provider_for_resource_level(
        self,
        level: ResourceLevel,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> BaseEmbeddingProvider:
        """
        Get embedding provider based on resource level.

        Args:
            level: Resource level (LOW/MEDIUM/HIGH)
            custom_config: Optional custom configuration overrides

        Returns:
            Configured embedding provider instance
        """
        default = self.DEFAULT_MODELS[level]
        provider_type = EmbeddingProvider(default["provider"])
        model_name = default["model"]

        # Override with custom config if provided
        if custom_config:
            provider_type = EmbeddingProvider(
                custom_config.get("provider", provider_type)
            )
            model_name = custom_config.get("model", model_name)

        config = EmbeddingConfig(
            provider=provider_type,
            model_name=model_name,
            batch_size=custom_config.get("batch_size", 100) if custom_config else 100,
            max_retries=custom_config.get("max_retries", 3) if custom_config else 3,
            retry_delay=custom_config.get("retry_delay", 1.0) if custom_config else 1.0,
            timeout=custom_config.get("timeout", 30.0) if custom_config else 30.0,
            api_key=custom_config.get("api_key") if custom_config else None,
            api_base=custom_config.get("api_base") if custom_config else None,
            ollama_host=custom_config.get("ollama_host", "http://localhost:11434")
            if custom_config
            else "http://localhost:11434",
            huggingface_device=custom_config.get("huggingface_device", "cpu")
            if custom_config
            else "cpu",
        )

        return self._create_provider(config)

    def _create_provider(self, config: EmbeddingConfig) -> BaseEmbeddingProvider:
        """Create a provider instance based on configuration."""
        providers = {
            EmbeddingProvider.OPENAI: OpenAIEmbeddingProvider,
            EmbeddingProvider.OLLAMA: OllamaEmbeddingProvider,
            EmbeddingProvider.HUGGINGFACE: HuggingFaceEmbeddingProvider,
        }

        provider_class = providers.get(config.provider)
        if not provider_class:
            raise EmbeddingError(f"Unknown provider: {config.provider}")

        return provider_class(config)

    async def embed_texts(
        self,
        texts: List[str],
        config: Optional[EmbeddingConfig] = None,
    ) -> EmbeddingResult:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            config: Optional embedding configuration (uses default if not provided)

        Returns:
            EmbeddingResult with embeddings and metadata
        """
        if config:
            provider = self._create_provider(config)
        elif self._provider:
            provider = self._provider
        elif self.config:
            provider = self._create_provider(self.config)
        else:
            raise EmbeddingError("No embedding configuration provided")

        return await provider.embed_texts(texts)

    async def embed_single(
        self,
        text: str,
        config: Optional[EmbeddingConfig] = None,
    ) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed
            config: Optional embedding configuration

        Returns:
            List of floats representing the embedding vector
        """
        result = await self.embed_texts([text], config)
        return result.embeddings[0]

    async def embed_for_dataset(
        self,
        texts: List[str],
        dataset_id: str,
    ) -> EmbeddingResult:
        """
        Generate embeddings using the configuration bound to a dataset.

        Args:
            texts: List of text strings to embed
            dataset_id: Dataset ID to look up configuration

        Returns:
            EmbeddingResult with embeddings and metadata
        """
        resource_config = ResourceConfigService.get_config_for_dataset(dataset_id)

        if not resource_config:
            raise EmbeddingError(
                f"No resource configuration found for dataset: {dataset_id}"
            )

        config_json = resource_config.config_json
        level = resource_config.level

        provider = self.get_provider_for_resource_level(level, config_json)
        return await provider.embed_texts(texts)

    async def health_check(self, config: Optional[EmbeddingConfig] = None) -> bool:
        """
        Check if the embedding provider is healthy.

        Args:
            config: Optional configuration to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            if config:
                provider = self._create_provider(config)
            elif self._provider:
                provider = self._provider
            elif self.config:
                provider = self._create_provider(self.config)
            else:
                return False

            return await provider.health_check()
        except Exception:
            return False

    def set_provider(self, provider: BaseEmbeddingProvider) -> None:
        """Set a custom provider instance."""
        self._provider = provider

    def configure(self, config: EmbeddingConfig) -> None:
        """Configure the service with a specific configuration."""
        self.config = config
        self._provider = self._create_provider(config)
