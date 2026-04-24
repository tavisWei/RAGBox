class DataStoreError(Exception):
    pass


class CollectionNotFoundError(DataStoreError):
    pass


class DocumentNotFoundError(DataStoreError):
    pass


class BackendNotAvailableError(DataStoreError):
    pass


class InvalidSearchMethodError(DataStoreError):
    pass


class ConfigurationError(DataStoreError):
    pass


class IndexingError(DataStoreError):
    pass
