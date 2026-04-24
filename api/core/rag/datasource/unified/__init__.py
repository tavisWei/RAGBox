from api.core.rag.datasource.unified.base_data_store import (
    BaseDataStore,
    DataStoreStats,
    Document,
    SearchResult,
)
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory
from api.core.rag.datasource.unified.exceptions import (
    BackendNotAvailableError,
    CollectionNotFoundError,
    ConfigurationError,
    DataStoreError,
    DocumentNotFoundError,
    IndexingError,
    InvalidSearchMethodError,
)
from api.core.rag.datasource.unified.sqlite_data_store import SQLiteDataStore

try:
    from api.core.rag.datasource.unified.pgvector_data_store import PGVectorDataStore
except ImportError:
    PGVectorDataStore = None  # type: ignore

try:
    from api.core.rag.datasource.unified.elasticsearch_data_store import (
        ElasticsearchDataStore,
    )
except ImportError:
    ElasticsearchDataStore = None  # type: ignore

__all__ = [
    "BaseDataStore",
    "DataStoreFactory",
    "DataStoreStats",
    "Document",
    "SearchResult",
    "SQLiteDataStore",
    "BackendNotAvailableError",
    "CollectionNotFoundError",
    "ConfigurationError",
    "DataStoreError",
    "DocumentNotFoundError",
    "IndexingError",
    "InvalidSearchMethodError",
]
