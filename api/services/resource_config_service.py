from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


class ResourceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResourceConfig:
    """Resource configuration model (standalone, no ORM dependency)."""

    def __init__(
        self,
        tenant_id: str,
        level: ResourceLevel,
        data_store_type: str,
        config_json: Dict[str, Any],
        is_default: bool = False,
        id: Optional[str] = None,
    ):
        self.id = id or ""
        self.tenant_id = tenant_id
        self.level = level
        self.data_store_type = data_store_type
        self.config_json = config_json
        self.is_default = is_default


class DatasetResourceBinding:
    """Dataset to resource config binding (standalone, no ORM dependency)."""

    def __init__(
        self,
        dataset_id: str,
        resource_config_id: str,
        id: Optional[str] = None,
    ):
        self.id = id or ""
        self.dataset_id = dataset_id
        self.resource_config_id = resource_config_id
        self.resource_config: Optional[ResourceConfig] = None


class ResourceConfigService:
    """
    Resource configuration service.

    Manages default configurations for low/medium/high resource levels
    and provides dataset-to-config binding lookups.
    """

    DEFAULT_CONFIGS: Dict[ResourceLevel, Dict[str, Any]] = {
        ResourceLevel.LOW: {
            "data_store_type": "sqlite",
            "vector_enabled": False,
            "keyword_enabled": True,
            "fulltext_enabled": True,
            "hybrid_fusion_method": "simple",
            "rerank_enabled": False,
            "max_documents": 10000,
            "embedding_provider": "ollama",
            "embedding_model": "nomic-embed-text",
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
        ResourceLevel.MEDIUM: {
            "data_store_type": "pgvector",
            "vector_enabled": True,
            "keyword_enabled": True,
            "fulltext_enabled": True,
            "hybrid_fusion_method": "rrf",
            "rerank_enabled": True,
            "max_documents": 1000000,
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
        ResourceLevel.HIGH: {
            "data_store_type": "elasticsearch",
            "vector_enabled": True,
            "keyword_enabled": True,
            "fulltext_enabled": True,
            "hybrid_fusion_method": "rrf",
            "rerank_enabled": True,
            "max_documents": 100000000,
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-large",
            "chunk_size": 1000,
            "chunk_overlap": 100,
        },
    }

    _configs: Dict[str, ResourceConfig] = {}
    _bindings: Dict[str, DatasetResourceBinding] = {}
    _default_config_id: Optional[str] = None

    @classmethod
    def get_default_config(cls, level: ResourceLevel) -> Dict[str, Any]:
        """Get the default configuration for a resource level."""
        return cls.DEFAULT_CONFIGS.get(
            level, cls.DEFAULT_CONFIGS[ResourceLevel.MEDIUM]
        ).copy()

    @classmethod
    def create_config(
        cls,
        tenant_id: str,
        level: ResourceLevel,
        custom_config: Optional[Dict[str, Any]] = None,
        config_id: Optional[str] = None,
    ) -> ResourceConfig:
        """Create a resource configuration for a tenant."""
        config = cls.get_default_config(level)
        if custom_config:
            config.update(custom_config)

        resource_config = ResourceConfig(
            tenant_id=tenant_id,
            level=level,
            data_store_type=config["data_store_type"],
            config_json=config,
            is_default=False,
            id=config_id,
        )

        cls._configs[resource_config.id] = resource_config
        return resource_config

    @classmethod
    def set_default_config(cls, config_id: str) -> None:
        """Set a configuration as the default for its tenant."""
        if config_id not in cls._configs:
            raise ValueError(f"Config '{config_id}' not found")
        cls._default_config_id = config_id

    @classmethod
    def get_config(cls, config_id: str) -> Optional[ResourceConfig]:
        """Get a configuration by ID."""
        return cls._configs.get(config_id)

    @classmethod
    def get_config_for_dataset(cls, dataset_id: str) -> Optional[ResourceConfig]:
        """
        Get the resource configuration for a dataset.

        1. Check if dataset has a specific binding
        2. Fall back to the default configuration
        """
        binding = cls._bindings.get(dataset_id)
        if binding and binding.resource_config:
            return binding.resource_config

        if binding and binding.resource_config_id in cls._configs:
            return cls._configs[binding.resource_config_id]

        if cls._default_config_id and cls._default_config_id in cls._configs:
            return cls._configs[cls._default_config_id]

        return None

    @classmethod
    def bind_dataset_to_config(
        cls, dataset_id: str, config_id: str
    ) -> DatasetResourceBinding:
        """Bind a dataset to a resource configuration."""
        if config_id not in cls._configs:
            raise ValueError(f"Config '{config_id}' not found")

        binding = DatasetResourceBinding(
            dataset_id=dataset_id,
            resource_config_id=config_id,
        )
        binding.resource_config = cls._configs[config_id]
        cls._bindings[dataset_id] = binding
        return binding

    @classmethod
    def unbind_dataset(cls, dataset_id: str) -> None:
        """Remove a dataset's resource configuration binding."""
        cls._bindings.pop(dataset_id, None)

    @classmethod
    def list_configs(cls, tenant_id: Optional[str] = None) -> List[ResourceConfig]:
        """List all configurations, optionally filtered by tenant."""
        configs = list(cls._configs.values())
        if tenant_id:
            configs = [c for c in configs if c.tenant_id == tenant_id]
        return configs

    @classmethod
    def delete_config(cls, config_id: str) -> None:
        """Delete a configuration and remove associated bindings."""
        if config_id not in cls._configs:
            raise ValueError(f"Config '{config_id}' not found")

        del cls._configs[config_id]

        if cls._default_config_id == config_id:
            cls._default_config_id = None

        to_remove = [
            dataset_id
            for dataset_id, binding in cls._bindings.items()
            if binding.resource_config_id == config_id
        ]
        for dataset_id in to_remove:
            del cls._bindings[dataset_id]

    @classmethod
    def reset(cls) -> None:
        """Reset all stored state (useful for testing)."""
        cls._configs.clear()
        cls._bindings.clear()
        cls._default_config_id = None
