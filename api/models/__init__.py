"""Models package for RAG platform"""

from .resource_config import (
    Base,
    ResourceConfig,
    ResourceLevel,
    DatasetResourceBinding,
    RetrievalMetrics,
)
from .app import App, AppMode, AppSiteConfig
from .conversation import (
    Conversation,
    Message,
    MessageStatus,
    MessageAnnotation,
)
from .dataset import Dataset, DatasetPermission, IndexingTechnique
from .document import Document, DataSourceType, IndexingStatus
from .document_segment import DocumentSegment, SegmentStatus

__all__ = [
    # Base
    "Base",
    # Resource config models
    "ResourceConfig",
    "ResourceLevel",
    "DatasetResourceBinding",
    "RetrievalMetrics",
    # App models
    "App",
    "AppMode",
    "AppSiteConfig",
    # Conversation models
    "Conversation",
    "Message",
    "MessageStatus",
    "MessageAnnotation",
    # Dataset models
    "Dataset",
    "DatasetPermission",
    "IndexingTechnique",
    # Document models
    "Document",
    "DataSourceType",
    "IndexingStatus",
    # Document segment models
    "DocumentSegment",
    "SegmentStatus",
]
