"""Model providers abstraction layer for unified LLM and Embedding model invocation."""

# Legacy imports (backward compatibility)
from api.core.model_providers.base import BaseModelProvider, BaseEmbeddingProvider
from api.core.model_providers.llm_types import (
    LLMResult as LegacyLLMResult,
    LLMUsage,
    LLMMessage,
)
from api.core.model_providers.embedding_types import (
    EmbeddingResult as LegacyEmbeddingResult,
    EmbeddingUsage,
)

# New provider system imports
from api.core.model_providers.base_provider import BaseProvider
from api.core.model_providers.model_instance import ModelInstance
from api.core.model_providers.provider_factory import ProviderFactory
from api.core.model_providers.entities import (
    ModelType,
    ProviderType,
    ProviderConfig,
    ModelConfig,
    LLMResult,
    EmbeddingResult,
    RerankResult,
)

__all__ = [
    # Legacy exports (backward compatibility)
    "BaseModelProvider",
    "BaseEmbeddingProvider",
    "LLMUsage",
    "LLMMessage",
    "EmbeddingUsage",
    # New provider system exports
    "BaseProvider",
    "ModelInstance",
    "ProviderFactory",
    "ModelType",
    "ProviderType",
    "ProviderConfig",
    "ModelConfig",
    "LLMResult",
    "EmbeddingResult",
    "RerankResult",
]
