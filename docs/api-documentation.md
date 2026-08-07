# API Documentation

This document describes the public APIs provided by the RAG Platform.

## Table of Contents

- [Data Store API](#data-store-api)
- [Retrieval API](#retrieval-api)
- [Resource Configuration API](#resource-configuration-api)
- [Data Models](#data-models)
- [Exceptions](#exceptions)

## Data Store API

The unified data layer provides a consistent interface across all storage backends.

### BaseDataStore

Abstract base class that all data store implementations extend.

#### Constructor

```python
BaseDataStore(config: Dict[str, Any])
```

All implementations accept a configuration dictionary. Specific keys vary by backend.

#### Methods

##### create_collection

```python
def create_collection(
    self,
    collection_name: str,
    dimension: Optional[int] = None
) -> None
```

Create a new collection (table, index) for storing documents.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| collection_name | str | Yes | Unique name for the collection |
| dimension | int | No | Vector dimension size (for vector-enabled stores) |

**Example:**

```python
store.create_collection("knowledge_base", dimension=768)
```

##### add_documents

```python
def add_documents(
    self,
    collection_name: str,
    documents: List[Document],
    embeddings: Optional[List[List[float]]] = None
) -> List[str]
```

Add documents to a collection. Returns the list of document IDs.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| collection_name | str | Yes | Target collection |
| documents | List[Document] | Yes | Documents to add |
| embeddings | List[List[float]] | No | Embedding vectors (one per document) |

**Returns:** List of document IDs

**Example:**

```python
docs = [
    Document(page_content="Hello world", metadata={"doc_id": "doc1"}),
    Document(page_content="Python guide", metadata={"doc_id": "doc2"}),
]
embeddings = [[1.0, 0.0], [0.0, 1.0]]
ids = store.add_documents("kb", docs, embeddings)
```

##### search

```python
def search(
    self,
    collection_name: str,
    query: str,
    query_vector: Optional[List[float]] = None,
    top_k: int = 10,
    score_threshold: float = 0.0,
    filters: Optional[Dict[str, Any]] = None,
    search_method: str = "hybrid"
) -> List[SearchResult]
```

Search for documents in a collection.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| collection_name | str | Yes | Collection to search |
| query | str | Yes | Query text |
| query_vector | List[float] | No | Query embedding vector |
| top_k | int | No | Max results to return (default: 10) |
| score_threshold | float | No | Minimum score cutoff (default: 0.0) |
| filters | Dict[str, Any] | No | Metadata filters |
| search_method | str | No | "semantic", "keyword", "fulltext", or "hybrid" |

**Returns:** List of SearchResult objects

**Example:**

```python
results = store.search(
    "kb",
    "Python programming",
    query_vector=[1.0, 0.0],
    top_k=5,
    search_method="hybrid"
)
for r in results:
    print(f"{r.doc_id}: {r.score} - {r.content[:50]}")
```

##### delete_documents

```python
def delete_documents(
    self,
    collection_name: str,
    doc_ids: List[str]
) -> None
```

Delete documents by their IDs.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| collection_name | str | Yes | Collection containing the documents |
| doc_ids | List[str] | Yes | IDs of documents to delete |

##### delete_collection

```python
def delete_collection(self, collection_name: str) -> None
```

Delete an entire collection and all its documents.

##### get_stats

```python
def get_stats(self, collection_name: str) -> DataStoreStats
```

Get statistics about a collection.

**Returns:** DataStoreStats object

##### health_check

```python
def health_check(self) -> bool
```

Check if the data store is accessible and functioning.

**Returns:** True if healthy, False otherwise

### DataStoreFactory

Factory for creating data store instances.

#### create

```python
@classmethod
def create(
    cls,
    store_type: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> BaseDataStore
```

Create a data store instance.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| store_type | str | No | Backend type (default: env var or "sqlite") |
| config | Dict[str, Any] | No | Backend-specific configuration |

**Example:**

```python
store = DataStoreFactory.create("sqlite", {"db_path": "data.db"})
store = DataStoreFactory.create("pgvector", {"host": "localhost", "port": 5432})
```

#### get_available_stores

```python
@classmethod
def get_available_stores(cls) -> List[str]
```

List all registered backend types.

**Returns:** List of backend names (e.g., ["sqlite", "pgvector", "elasticsearch"])

#### register

```python
@classmethod
def register(cls, name: str, store_class: Type[BaseDataStore]) -> None
```

Register a custom data store backend.

## Retrieval API

### MultiWayRetriever

Orchestrates parallel retrieval from multiple search methods.

#### Constructor

```python
MultiWayRetriever(
    data_store: BaseDataStore,
    fusion_method: str = "rrf",
    reranker: Optional[Reranker] = None,
    max_workers: int = 3
)
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| data_store | BaseDataStore | Yes | Data store instance |
| fusion_method | str | No | Fusion strategy: "rrf" (default) |
| reranker | Reranker | No | Optional reranker instance |
| max_workers | int | No | Thread pool size (default: 3) |

#### retrieve

```python
def retrieve(
    self,
    collection_name: str,
    query: str,
    query_vector: Optional[List[float]] = None,
    top_k: int = 10,
    score_threshold: float = 0.0,
    filters: Optional[Dict[str, Any]] = None,
    methods: Optional[List[str]] = None
) -> List[SearchResult]
```

Retrieve documents using multiple methods in parallel.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| collection_name | str | Yes | Target collection |
| query | str | Yes | Query text |
| query_vector | List[float] | No | Query embedding |
| top_k | int | No | Number of results (default: 10) |
| score_threshold | float | No | Score cutoff (default: 0.0) |
| filters | Dict[str, Any] | No | Metadata filters |
| methods | List[str] | No | Methods: ["vector", "fulltext"] (default: both) |

**Example:**

```python
retriever = MultiWayRetriever(store)
results = retriever.retrieve(
    "kb",
    "machine learning",
    query_vector=[0.1, 0.9],
    methods=["vector", "fulltext"],
    top_k=10
)
```

### Reranker

Post-processes retrieval results with a reranking model.

#### Constructor

```python
Reranker(
    rerank_fn: Optional[Callable] = None,
    model_name: str = "noop",
    top_k: int = 10
)
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| rerank_fn | Callable | No | Custom reranking function |
| model_name | str | No | Model identifier (default: "noop") |
| top_k | int | No | Max results after reranking |

#### rerank

```python
def rerank(
    self,
    query: str,
    results: List[SearchResult]
) -> List[SearchResult]
```

Rerank search results.

**Example:**

```python
def bge_rerank(query, results):
    # Your reranking logic
    return [(result, new_score) for result, new_score in ...]

reranker = Reranker(rerank_fn=bge_rerank, model_name="bge-reranker")
reranked = reranker.rerank("query", results)
```

### Fusion Strategies

#### reciprocal_rank_fusion

```python
def reciprocal_rank_fusion(
    result_lists: List[List[SearchResult]],
    k: float = 60.0
) -> List[SearchResult]
```

Combines multiple ranked lists using Reciprocal Rank Fusion.

Score = sum(1 / (k + rank)) across all lists.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| result_lists | List[List[SearchResult]] | Yes | Multiple result lists |
| k | float | No | RRF constant (default: 60.0) |

#### weighted_score_fusion

```python
def weighted_score_fusion(
    result_lists: List[List[SearchResult]],
    weights: List[float]
) -> List[SearchResult]
```

Combines result lists using weighted score fusion.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| result_lists | List[List[SearchResult]] | Yes | Multiple result lists |
| weights | List[float] | Yes | Weight for each list |

## Resource Configuration API

### ResourceConfigService

Manages resource configurations and dataset bindings.

#### get_default_config

```python
@classmethod
def get_default_config(cls, level: ResourceLevel) -> Dict[str, Any]
```

Get default configuration for a resource level.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| level | ResourceLevel | Yes | LOW, MEDIUM, or HIGH |

**Returns:** Configuration dictionary

**Example:**

```python
config = ResourceConfigService.get_default_config(ResourceLevel.MEDIUM)
# Returns:
# {
#     "data_store_type": "pgvector",
#     "vector_enabled": True,
#     "rerank_enabled": True,
#     "max_documents": 1000000,
#     ...
# }
```

#### create_config

```python
@classmethod
def create_config(
    cls,
    tenant_id: str,
    level: ResourceLevel,
    custom_config: Optional[Dict[str, Any]] = None,
    config_id: Optional[str] = None
) -> ResourceConfig
```

Create a resource configuration.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| tenant_id | str | Yes | Tenant identifier |
| level | ResourceLevel | Yes | Resource level |
| custom_config | Dict[str, Any] | No | Override default settings |
| config_id | str | No | Custom config ID |

#### get_config

```python
@classmethod
def get_config(cls, config_id: str) -> Optional[ResourceConfig]
```

Get a configuration by ID.

#### get_config_for_dataset

```python
@classmethod
def get_config_for_dataset(cls, dataset_id: str) -> Optional[ResourceConfig]
```

Get the configuration for a dataset. Checks bindings first, then falls back to default.

#### bind_dataset_to_config

```python
@classmethod
def bind_dataset_to_config(
    cls,
    dataset_id: str,
    config_id: str
) -> DatasetResourceBinding
```

Bind a dataset to a specific configuration.

#### unbind_dataset

```python
@classmethod
def unbind_dataset(cls, dataset_id: str) -> None
```

Remove a dataset's configuration binding.

#### list_configs

```python
@classmethod
def list_configs(cls, tenant_id: Optional[str] = None) -> List[ResourceConfig]
```

List all configurations, optionally filtered by tenant.

#### delete_config

```python
@classmethod
def delete_config(cls, config_id: str) -> None
```

Delete a configuration and remove associated bindings.

#### set_default_config

```python
@classmethod
def set_default_config(cls, config_id: str) -> None
```

Set a configuration as the default for unbound datasets.

## Data Models

### Document

```python
@dataclass
class Document:
    page_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Represents a document to be stored and retrieved.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| page_content | str | The document text content |
| metadata | Dict[str, Any] | Arbitrary metadata (include "doc_id" for custom IDs) |

### SearchResult

```python
@dataclass
class SearchResult:
    content: str
    score: float
    doc_id: str
    metadata: Dict[str, Any]
    retrieval_method: str
```

Represents a single search result.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| content | str | Matched document content |
| score | float | Relevance score |
| doc_id | str | Document identifier |
| metadata | Dict[str, Any] | Document metadata |
| retrieval_method | str | How this result was found: "vector", "fulltext", "fusion_rrf", "reranked_*" |

### DataStoreStats

```python
@dataclass
class DataStoreStats:
    total_documents: int
    total_chunks: int
    index_size_bytes: int
    avg_query_latency_ms: float
    backend_type: str
```

Statistics for a collection.

### ResourceLevel

```python
class ResourceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

### ResourceConfig

```python
class ResourceConfig:
    id: str
    tenant_id: str
    level: ResourceLevel
    data_store_type: str
    config_json: Dict[str, Any]
    is_default: bool
```

### DatasetResourceBinding

```python
class DatasetResourceBinding:
    id: str
    dataset_id: str
    resource_config_id: str
    resource_config: Optional[ResourceConfig]
```

## Exceptions

| Exception | Description |
|-----------|-------------|
| DataStoreError | Base exception for all data store errors |
| CollectionNotFoundError | Collection or index does not exist |
| DocumentNotFoundError | Document not found |
| BackendNotAvailableError | Requested backend is not installed or configured |
| InvalidSearchMethodError | Unknown search method specified |
| ConfigurationError | Invalid configuration provided |
| IndexingError | Failed to index documents |

**Example:**

```python
from api.core.rag.datasource.unified.exceptions import CollectionNotFoundError

try:
    results = store.search("missing_collection", "query")
except CollectionNotFoundError:
    print("Collection does not exist")
```

## Agent RAG API（主动检索）

知识库选择 `agent` 方案（`rag_plan=agent`，KB 记录上体现为 `rag_mode="agent"`）后启用主动检索。

### 导入期

`POST /knowledge-bases/{kb_id}/documents` 与 `/documents/upload` 完成后，后台任务（FastAPI `BackgroundTasks`）为每个文档生成索引条目：LLM 产出 `{title, summary, keywords, questions}`，写入 `agent_rag_index` namespace，并向量化到 `{kb_id}__agent_index` collection。条目状态：`pending → indexing → completed/error`。文档删除时联动移除条目并重建索引集合；知识库删除时清理全部索引。

### 索引管理端点

- `GET /knowledge-bases/{kb_id}/agent-index` → `{data: AgentIndexEntry[], rag_mode}`，前端以 3s 轮询跟踪 pending/indexing 状态。
- `POST /knowledge-bases/{kb_id}/agent-index/rebuild` → 后台按数据存储中的分块（按 `metadata.document_id` 分组重建原文）全量重建索引；无默认模型供应商时返回 400。

### 对话期

`ChatService` 按 KB 的 `rag_mode` 分流：agent 模式 KB 走 `AgentRAGService`（`api/services/agent_rag_service.py`），主内核为 langgraph `create_react_agent`（注册 `kb_search` / `kb_list_documents` 两个工具，sqlite checkpointer 按 conversation_id 持久化会话状态，重启不丢），由 LLM 自主决定何时检索、检索几次；工具内部两段式取料（索引摘要层定位候选文档 → 块级分片按 `document_id` 过滤，过滤为空退回全量）。降级链：langgraph 内核 → 自研 `FunctionCallAgentRunner` → 标准 RAG 检索。

流式协议保持 `text/plain`：Agent 事件以 `@@AGENT_EVENT@@` 前缀的单行 JSON 帧混入流（`stage`: `think|tool_call|tool_result|fallback|error|sources`），前端按行解析，事件帧不计入回答正文；`sources` 帧同时持久化到消息的 `message_metadata.agent_sources`。
