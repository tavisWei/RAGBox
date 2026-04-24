"""Tests for model provider base classes and factory."""

from __future__ import annotations

import pytest
from typing import List, Optional
from unittest.mock import MagicMock

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


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    async def invoke_llm(
        self,
        model: ModelConfig,
        prompt: str,
        **kwargs,
    ) -> LLMResult:
        return LLMResult(
            content=f"Response to: {prompt}",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
            model=model.model_name,
        )

    async def stream_llm(
        self,
        model: ModelConfig,
        prompt: str,
        **kwargs,
    ):
        tokens = ["Response", " to: ", prompt]
        for token in tokens:
            yield token

    async def invoke_embedding(
        self,
        model: ModelConfig,
        texts: List[str],
        **kwargs,
    ) -> EmbeddingResult:
        embeddings = [[0.1, 0.2, 0.3] for _ in texts]
        return EmbeddingResult(
            embeddings=embeddings,
            usage={"total_tokens": len(texts) * 10},
            model=model.model_name,
        )

    def list_models(self, model_type: Optional[ModelType] = None) -> List[str]:
        all_models = {
            ModelType.LLM: ["gpt-4", "gpt-3.5-turbo"],
            ModelType.EMBEDDING: ["text-embedding-ada-002"],
            ModelType.RERANK: ["rerank-model"],
        }
        if model_type is None:
            return [m for models in all_models.values() for m in models]
        return all_models.get(model_type, [])

    def validate_credentials(self) -> bool:
        return self.config.api_key is not None


class TestProviderEntities:
    """Tests for provider entity classes."""

    def test_model_type_enum_values(self):
        assert ModelType.LLM.value == "llm"
        assert ModelType.EMBEDDING.value == "embedding"
        assert ModelType.RERANK.value == "rerank"

    def test_provider_type_enum_values(self):
        assert ProviderType.BUILTIN.value == "builtin"
        assert ProviderType.CUSTOM.value == "custom"

    def test_provider_config_defaults(self):
        config = ProviderConfig(provider_name="test")
        assert config.provider_name == "test"
        assert config.provider_type == ProviderType.BUILTIN
        assert config.api_key is None
        assert config.api_base is None
        assert config.credentials == {}

    def test_provider_config_with_credentials(self):
        config = ProviderConfig(
            provider_name="openai",
            api_key="sk-test",
            api_base="https://api.openai.com/v1",
            credentials={"org_id": "org-123"},
        )
        assert config.provider_name == "openai"
        assert config.api_key == "sk-test"
        assert config.api_base == "https://api.openai.com/v1"
        assert config.credentials["org_id"] == "org-123"

    def test_model_config_defaults(self):
        config = ModelConfig(
            model_name="gpt-4",
            model_type=ModelType.LLM,
            provider="openai",
        )
        assert config.model_name == "gpt-4"
        assert config.model_type == ModelType.LLM
        assert config.provider == "openai"
        assert config.parameters == {}
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_model_config_temperature_validation(self):
        config = ModelConfig(
            model_name="gpt-4",
            model_type=ModelType.LLM,
            provider="openai",
            temperature=1.5,
        )
        assert config.temperature == 1.5

    def test_llm_result_properties(self):
        result = LLMResult(
            content="Hello",
            usage={"prompt_tokens": 5, "completion_tokens": 3},
            finish_reason="stop",
        )
        assert result.is_complete is True
        assert result.is_truncated is False

    def test_llm_result_truncated(self):
        result = LLMResult(
            content="Hello",
            finish_reason="length",
        )
        assert result.is_complete is False
        assert result.is_truncated is True

    def test_embedding_result_properties(self):
        result = EmbeddingResult(
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            usage={"total_tokens": 20},
        )
        assert result.count == 2
        assert result.is_empty is False
        assert result.dimension == 2

    def test_embedding_result_empty(self):
        result = EmbeddingResult(embeddings=[])
        assert result.count == 0
        assert result.is_empty is True
        assert result.dimension is None

    def test_rerank_result_properties(self):
        result = RerankResult(
            results=[
                {"index": 0, "score": 0.9},
                {"index": 1, "score": 0.7},
            ],
        )
        assert result.count == 2


class TestBaseProvider:
    """Tests for BaseProvider abstract class."""

    @pytest.fixture
    def provider_config(self):
        return ProviderConfig(
            provider_name="mock",
            api_key="test-key",
        )

    @pytest.fixture
    def provider(self, provider_config):
        return MockProvider(provider_config)

    def test_provider_initialization(self, provider, provider_config):
        assert provider.config == provider_config
        assert provider.provider_name == "mock"
        assert provider.provider_type == "builtin"

    def test_provider_name_property(self, provider):
        assert provider.provider_name == "mock"

    def test_provider_type_property(self, provider):
        assert provider.provider_type == "builtin"

    def test_list_models_all(self, provider):
        models = provider.list_models()
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
        assert "text-embedding-ada-002" in models

    def test_list_models_by_type(self, provider):
        llm_models = provider.list_models(ModelType.LLM)
        assert llm_models == ["gpt-4", "gpt-3.5-turbo"]

        embedding_models = provider.list_models(ModelType.EMBEDDING)
        assert embedding_models == ["text-embedding-ada-002"]

    def test_validate_credentials_success(self, provider):
        assert provider.validate_credentials() is True

    def test_validate_credentials_failure(self):
        config = ProviderConfig(provider_name="mock")
        provider = MockProvider(config)
        assert provider.validate_credentials() is False

    def test_get_model_config(self, provider):
        config = provider.get_model_config("gpt-4", ModelType.LLM)
        assert config.model_name == "gpt-4"
        assert config.model_type == ModelType.LLM
        assert config.provider == "mock"

    def test_get_model_instance(self, provider):
        instance = provider.get_model_instance("gpt-4", ModelType.LLM)
        assert instance.__class__.__name__ == "ModelInstance"
        assert instance.model_name == "gpt-4"
        assert instance.model_type == ModelType.LLM

    def test_supports_model_type(self, provider):
        assert provider.supports_model_type(ModelType.LLM) is True
        assert provider.supports_model_type(ModelType.EMBEDDING) is True
        assert provider.supports_model_type(ModelType.RERANK) is True

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        config = ProviderConfig(provider_name="mock")
        provider = MockProvider(config)
        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_invoke_llm(self, provider):
        model_config = ModelConfig(
            model_name="gpt-4",
            model_type=ModelType.LLM,
            provider="mock",
        )
        result = await provider.invoke_llm(model_config, "Hello")
        assert result.content == "Response to: Hello"
        assert result.model == "gpt-4"
        assert result.is_complete is True

    @pytest.mark.asyncio
    async def test_stream_llm(self, provider):
        model_config = ModelConfig(
            model_name="gpt-4",
            model_type=ModelType.LLM,
            provider="mock",
        )
        tokens = []
        async for token in provider.stream_llm(model_config, "Hello"):
            tokens.append(token)
        assert tokens == ["Response", " to: ", "Hello"]

    @pytest.mark.asyncio
    async def test_invoke_embedding(self, provider):
        model_config = ModelConfig(
            model_name="text-embedding-ada-002",
            model_type=ModelType.EMBEDDING,
            provider="mock",
        )
        result = await provider.invoke_embedding(model_config, ["Hello", "World"])
        assert result.count == 2
        assert result.dimension == 3
        assert result.model == "text-embedding-ada-002"


class TestModelInstance:
    """Tests for ModelInstance wrapper class."""

    @pytest.fixture
    def provider(self):
        config = ProviderConfig(provider_name="mock", api_key="test-key")
        return MockProvider(config)

    @pytest.fixture
    def llm_instance(self, provider):
        return provider.get_model_instance("gpt-4", ModelType.LLM)

    @pytest.fixture
    def embedding_instance(self, provider):
        return provider.get_model_instance(
            "text-embedding-ada-002", ModelType.EMBEDDING
        )

    def test_instance_properties(self, llm_instance, provider):
        assert llm_instance.provider == provider
        assert llm_instance.model_name == "gpt-4"
        assert llm_instance.model_type == ModelType.LLM

    def test_model_config_lazy_creation(self, llm_instance):
        config = llm_instance.model_config
        assert config.model_name == "gpt-4"
        assert config.model_type == ModelType.LLM
        assert config.provider == "mock"

    def test_repr(self, llm_instance):
        repr_str = repr(llm_instance)
        assert "ModelInstance" in repr_str
        assert "gpt-4" in repr_str
        assert "llm" in repr_str

    @pytest.mark.asyncio
    async def test_invoke_llm(self, llm_instance):
        result = await llm_instance.invoke("Hello")
        assert result.content == "Response to: Hello"
        assert result.is_complete is True

    @pytest.mark.asyncio
    async def test_invoke_non_llm_raises(self, embedding_instance):
        with pytest.raises(ValueError) as exc_info:
            await embedding_instance.invoke("Hello")
        assert "not an LLM model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_llm(self, llm_instance):
        tokens = []
        async for token in llm_instance.stream("Hello"):
            tokens.append(token)
        assert tokens == ["Response", " to: ", "Hello"]

    @pytest.mark.asyncio
    async def test_stream_non_llm_raises(self, embedding_instance):
        with pytest.raises(ValueError) as exc_info:
            async for _ in embedding_instance.stream("Hello"):
                pass
        assert "not an LLM model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed(self, embedding_instance):
        result = await embedding_instance.embed(["Hello", "World"])
        assert result.count == 2
        assert result.dimension == 3

    @pytest.mark.asyncio
    async def test_embed_non_embedding_raises(self, llm_instance):
        with pytest.raises(ValueError) as exc_info:
            await llm_instance.embed(["Hello"])
        assert "not an embedding model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rerank_non_rerank_raises(self, llm_instance):
        with pytest.raises(ValueError) as exc_info:
            await llm_instance.rerank("query", ["doc1", "doc2"])
        assert "not a rerank model" in str(exc_info.value)


class TestProviderFactory:
    """Tests for ProviderFactory."""

    def setup_method(self):
        ProviderFactory.clear()

    def teardown_method(self):
        ProviderFactory.clear()

    def test_register_decorator(self):
        @ProviderFactory.register("test_provider")
        class TestProvider(MockProvider):
            pass

        assert ProviderFactory.is_registered("test_provider")
        assert "test_provider" in ProviderFactory.list_providers()

    def test_register_case_insensitive(self):
        @ProviderFactory.register("TestProvider")
        class TestProvider(MockProvider):
            pass

        assert ProviderFactory.is_registered("testprovider")
        assert ProviderFactory.is_registered("TESTPROVIDER")

    def test_create_provider(self):
        @ProviderFactory.register("mock")
        class RegisteredMockProvider(MockProvider):
            pass

        config = ProviderConfig(provider_name="mock", api_key="test")
        provider = ProviderFactory.create(config)
        assert isinstance(provider, RegisteredMockProvider)
        assert provider.config == config

    def test_create_unknown_provider_raises(self):
        config = ProviderConfig(provider_name="unknown")
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.create(config)
        assert "Unknown provider" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)

    def test_list_providers_empty(self):
        assert ProviderFactory.list_providers() == []

    def test_list_providers_multiple(self):
        @ProviderFactory.register("provider1")
        class Provider1(MockProvider):
            pass

        @ProviderFactory.register("provider2")
        class Provider2(MockProvider):
            pass

        providers = ProviderFactory.list_providers()
        assert len(providers) == 2
        assert "provider1" in providers
        assert "provider2" in providers

    def test_is_registered(self):
        assert ProviderFactory.is_registered("nonexistent") is False

        @ProviderFactory.register("existing")
        class ExistingProvider(MockProvider):
            pass

        assert ProviderFactory.is_registered("existing") is True

    def test_get_provider_class(self):
        @ProviderFactory.register("test")
        class TestProvider(MockProvider):
            pass

        cls = ProviderFactory.get_provider_class("test")
        assert cls is TestProvider

        assert ProviderFactory.get_provider_class("nonexistent") is None

    def test_unregister(self):
        @ProviderFactory.register("to_remove")
        class ToRemoveProvider(MockProvider):
            pass

        assert ProviderFactory.is_registered("to_remove")
        result = ProviderFactory.unregister("to_remove")
        assert result is True
        assert not ProviderFactory.is_registered("to_remove")

        result = ProviderFactory.unregister("nonexistent")
        assert result is False

    def test_clear(self):
        @ProviderFactory.register("provider1")
        class Provider1(MockProvider):
            pass

        @ProviderFactory.register("provider2")
        class Provider2(MockProvider):
            pass

        assert len(ProviderFactory.list_providers()) == 2
        ProviderFactory.clear()
        assert ProviderFactory.list_providers() == []


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy imports."""

    def test_legacy_imports_available(self):
        from api.core.model_providers import (
            BaseModelProvider,
            BaseEmbeddingProvider,
            LLMUsage,
            LLMMessage,
            EmbeddingUsage,
        )

        assert BaseModelProvider is not None
        assert BaseEmbeddingProvider is not None
        assert LLMUsage is not None
        assert LLMMessage is not None
        assert EmbeddingUsage is not None

    def test_new_imports_available(self):
        from api.core.model_providers import (
            BaseProvider,
            ModelInstance,
            ProviderFactory,
            ModelType,
            ProviderType,
            ProviderConfig,
            ModelConfig,
            LLMResult,
            EmbeddingResult,
            RerankResult,
        )

        assert BaseProvider is not None
        assert ModelInstance is not None
        assert ProviderFactory is not None
        assert ModelType is not None
        assert ProviderType is not None
        assert ProviderConfig is not None
        assert ModelConfig is not None
        assert LLMResult is not None
        assert EmbeddingResult is not None
        assert RerankResult is not None
