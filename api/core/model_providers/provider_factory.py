"""Factory for creating model provider instances."""

from __future__ import annotations

from typing import Type

from api.core.model_providers.base_provider import BaseProvider
from api.core.model_providers.entities.provider_entities import ProviderConfig


class ProviderFactory:
    """Factory for creating and managing model providers.

    Provides a registry-based approach for instantiating providers
    by name, enabling dynamic provider registration and discovery.
    """

    _providers: dict[str, Type[BaseProvider]] = {}

    @classmethod
    def register(cls, name: str) -> callable:
        """Decorator to register a provider class.

        Args:
            name: Provider name for registration

        Returns:
            Decorator function that registers the provider

        Example:
            @ProviderFactory.register("openai")
            class OpenAIProvider(BaseProvider):
                ...
        """

        def decorator(provider_class: Type[BaseProvider]) -> Type[BaseProvider]:
            cls._providers[name.lower()] = provider_class
            return provider_class

        return decorator

    @classmethod
    def create(cls, config: ProviderConfig) -> BaseProvider:
        """Create a provider instance from configuration.

        Args:
            config: Provider configuration

        Returns:
            Instantiated provider

        Raises:
            ValueError: If provider is not registered
        """
        provider_name = config.provider_name.lower()
        if provider_name not in cls._providers:
            available = ", ".join(cls.list_providers()) or "none"
            raise ValueError(
                f"Unknown provider: '{config.provider_name}'. "
                f"Available providers: {available}"
            )

        provider_class = cls._providers[provider_name]
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names.

        Returns:
            List of registered provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a provider is registered.

        Args:
            name: Provider name to check

        Returns:
            True if registered, False otherwise
        """
        return name.lower() in cls._providers

    @classmethod
    def get_provider_class(cls, name: str) -> Type[BaseProvider] | None:
        """Get the provider class by name.

        Args:
            name: Provider name

        Returns:
            Provider class if registered, None otherwise
        """
        return cls._providers.get(name.lower())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a provider.

        Args:
            name: Provider name to unregister

        Returns:
            True if unregistered, False if not found
        """
        name_lower = name.lower()
        if name_lower in cls._providers:
            del cls._providers[name_lower]
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """Clear all registered providers."""
        cls._providers.clear()


__all__ = ["ProviderFactory"]
