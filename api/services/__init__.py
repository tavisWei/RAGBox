"""Services package for RAG platform."""

from api.services.embedding_service import (
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingError,
    ModelNotFoundError,
    EmbeddingProviderError,
)
from api.services.llm_service import (
    LLMService,
    ChatMessage,
    ChatCompletion,
    ChatConfig,
    LLMError,
    RateLimitError,
    ModelNotFoundError as LLMModelNotFoundError,
)
from api.services.document_processor import (
    DocumentProcessor,
    ProcessedDocument,
    DocumentChunk,
    DocumentMetadata,
    ProcessorConfig,
    ChunkingStrategy,
    DocumentError,
    UnsupportedFormatError,
    create_document_processor,
)
from api.services.resource_config_service import (
    ResourceConfigService,
    ResourceLevel,
    ResourceConfig,
    DatasetResourceBinding,
)
from api.services.rag_service import (
    RAGService,
    RAGResponse,
    RAGSource,
    create_rag_service,
)
from api.services.app_service import (
    AppService,
    get_app_service,
)
from api.services.chat_service import (
    ChatService,
    get_chat_service,
)

__all__ = [
    # Embedding
    "EmbeddingService",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    "EmbeddingError",
    "ModelNotFoundError",
    "EmbeddingProviderError",
    # LLM
    "LLMService",
    "ChatMessage",
    "ChatCompletion",
    "ChatConfig",
    "LLMError",
    "RateLimitError",
    "LLMModelNotFoundError",
    # Document
    "DocumentProcessor",
    "ProcessedDocument",
    "DocumentChunk",
    "DocumentMetadata",
    "ProcessorConfig",
    "ChunkingStrategy",
    "DocumentError",
    "UnsupportedFormatError",
    "create_document_processor",
    # Resource
    "ResourceConfigService",
    "ResourceLevel",
    "ResourceConfig",
    "DatasetResourceBinding",
    # RAG
    "RAGService",
    "RAGResponse",
    "RAGSource",
    "create_rag_service",
    # App
    "AppService",
    "get_app_service",
    # Chat
    "ChatService",
    "get_chat_service",
]
