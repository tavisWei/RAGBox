from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Type

from .base_data_store import BaseDataStore
from .exceptions import BackendNotAvailableError
from .sqlite_data_store import SQLiteDataStore


class DataStoreFactory:
    _registry: Dict[str, Type[BaseDataStore]] = {
        "sqlite": SQLiteDataStore,
    }

    @classmethod
    def _register_builtin_backends(cls) -> None:
        """Lazily register optional backends to avoid import-time dependencies."""
        if "pgvector" not in cls._registry:
            try:
                from .pgvector_data_store import PGVectorDataStore
                cls._registry["pgvector"] = PGVectorDataStore
            except ImportError:
                pass

        if "elasticsearch" not in cls._registry:
            try:
                from .elasticsearch_data_store import ElasticsearchDataStore
                cls._registry["elasticsearch"] = ElasticsearchDataStore
            except ImportError:
                pass

    @classmethod
    def register(cls, name: str, store_class: Type[BaseDataStore]) -> None:
        cls._registry[name] = store_class

    @classmethod
    def create(
        cls, store_type: Optional[str] = None, config: Optional[Dict[str, Any]] = None
    ) -> BaseDataStore:
        cls._register_builtin_backends()
        store_type = store_type or os.getenv("DATA_STORE_TYPE", "sqlite")
        if store_type not in cls._registry:
            raise BackendNotAvailableError(
                f"Unknown data store type: {store_type}. "
                f"Available: {list(cls._registry.keys())}"
            )
        store_class = cls._registry[store_type]
        return store_class(config or {})

    @classmethod
    def get_available_stores(cls) -> List[str]:
        cls._register_builtin_backends()
        return list(cls._registry.keys())
