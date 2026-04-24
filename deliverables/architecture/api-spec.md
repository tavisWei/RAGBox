# API 设计文档

## 1. 概述

本文档定义 RAG 私有化专业知识问答平台的 API 规范，包括新增 API 和对 Dify 现有 API 的扩展。

## 2. 设计原则

- **RESTful 风格**：遵循 REST 设计规范
- **JSON 格式**：请求和响应均使用 JSON
- **版本控制**：URL 路径版本 `/api/v1/`
- **认证方式**：Bearer Token（复用 Dify 认证体系）
- **错误处理**：统一错误响应格式

## 3. 认证与授权

### 3.1 认证方式

```http
Authorization: Bearer {API_KEY}
```

### 3.2 权限控制

| 角色 | 资源配置 | 知识库管理 | 监控查看 | 系统设置 |
|------|---------|-----------|---------|---------|
| 系统管理员 | ✅ | ✅ | ✅ | ✅ |
| 知识库管理员 | 只读 | ✅ | 只读 | ❌ |
| 普通用户 | ❌ | 只读 | ❌ | ❌ |

## 4. API 端点

### 4.1 资源配置 API

#### 4.1.1 获取资源配置列表

```http
GET /api/v1/resource-configs
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| level | string | 否 | 按级别筛选：low/medium/high |
| is_default | boolean | 否 | 筛选默认配置 |
| page | integer | 否 | 页码，默认 1 |
| limit | integer | 否 | 每页数量，默认 20 |

**响应示例：**

```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Default Medium Config",
      "description": "Default configuration for medium resource level",
      "level": "medium",
      "data_store_type": "pgvector",
      "config_json": {
        "host": "localhost",
        "port": 5432,
        "database": "dify",
        "vector_enabled": true,
        "keyword_enabled": true,
        "fulltext_enabled": true,
        "hybrid_fusion_method": "rrf",
        "rerank_enabled": true,
        "max_documents": 1000000,
        "embedding_model": "text-embedding-3-small",
        "chunk_size": 500,
        "chunk_overlap": 50
      },
      "is_default": true,
      "is_active": true,
      "created_at": "2024-01-15T08:30:00Z",
      "updated_at": "2024-01-15T08:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 3,
    "total_pages": 1
  }
}
```

#### 4.1.2 创建资源配置

```http
POST /api/v1/resource-configs
```

**请求体：**

```json
{
  "name": "Custom High Config",
  "description": "Custom configuration for high resource level",
  "level": "high",
  "data_store_type": "elasticsearch",
  "config_json": {
    "hosts": ["http://es01:9200", "http://es02:9200"],
    "vector_enabled": true,
    "keyword_enabled": true,
    "fulltext_enabled": true,
    "hybrid_fusion_method": "rrf",
    "rerank_enabled": true,
    "max_documents": 100000000,
    "embedding_model": "text-embedding-3-large",
    "chunk_size": 1000,
    "chunk_overlap": 100
  },
  "is_default": false
}
```

**响应示例：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Custom High Config",
  "description": "Custom configuration for high resource level",
  "level": "high",
  "data_store_type": "elasticsearch",
  "config_json": {
    "hosts": ["http://es01:9200", "http://es02:9200"],
    "vector_enabled": true,
    "keyword_enabled": true,
    "fulltext_enabled": true,
    "hybrid_fusion_method": "rrf",
    "rerank_enabled": true,
    "max_documents": 100000000,
    "embedding_model": "text-embedding-3-large",
    "chunk_size": 1000,
    "chunk_overlap": 100
  },
  "is_default": false,
  "is_active": true,
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T09:00:00Z"
}
```

**错误响应：**

```json
{
  "error": {
    "code": "INVALID_CONFIG",
    "message": "Invalid configuration: hosts must be a non-empty array",
    "details": {
      "field": "config_json.hosts",
      "issue": "empty_array"
    }
  }
}
```

#### 4.1.3 获取资源配置详情

```http
GET /api/v1/resource-configs/{config_id}
```

**响应示例：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Custom High Config",
  "level": "high",
  "data_store_type": "elasticsearch",
  "config_json": {
    "hosts": ["http://es01:9200", "http://es02:9200"],
    "vector_enabled": true,
    "keyword_enabled": true,
    "fulltext_enabled": true,
    "hybrid_fusion_method": "rrf",
    "rerank_enabled": true
  },
  "is_default": false,
  "is_active": true,
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T09:00:00Z"
}
```

#### 4.1.4 更新资源配置

```http
PUT /api/v1/resource-configs/{config_id}
```

**请求体：**

```json
{
  "name": "Updated High Config",
  "config_json": {
    "hosts": ["http://es01:9200", "http://es02:9200", "http://es03:9200"],
    "vector_enabled": true,
    "keyword_enabled": true,
    "fulltext_enabled": true,
    "hybrid_fusion_method": "rrf",
    "rerank_enabled": true
  }
}
```

**注意：** 更新配置后，已绑定的知识库不会自动生效，需要手动触发重建。

#### 4.1.5 删除资源配置

```http
DELETE /api/v1/resource-configs/{config_id}
```

**约束：** 默认配置和有绑定关系的配置不能被删除。

**错误响应：**

```json
{
  "error": {
    "code": "CONFIG_IN_USE",
    "message": "Cannot delete configuration that is currently in use",
    "details": {
      "bound_datasets": 5,
      "dataset_ids": ["..."]
    }
  }
}
```

#### 4.1.6 测试配置连接

```http
POST /api/v1/resource-configs/{config_id}/test-connection
```

**响应示例：**

```json
{
  "success": true,
  "message": "Connection successful",
  "details": {
    "latency_ms": 15,
    "version": "8.11.0",
    "cluster_status": "green"
  }
}
```

**错误响应：**

```json
{
  "success": false,
  "message": "Connection failed",
  "details": {
    "error": "Connection refused",
    "host": "es01:9200"
  }
}
```

#### 4.1.7 应用配置到系统

```http
POST /api/v1/resource-configs/{config_id}/apply
```

**请求体：**

```json
{
  "scope": "system",  // "system" | "dataset"
  "dataset_id": null  // 当 scope=dataset 时必填
}
```

**响应示例：**

```json
{
  "success": true,
  "message": "Configuration applied successfully",
  "affected_datasets": 0,
  "rebuild_required": false
}
```

### 4.2 知识库资源绑定 API

#### 4.2.1 获取知识库资源绑定

```http
GET /api/v1/datasets/{dataset_id}/resource-binding
```

**响应示例：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440004",
  "resource_config_id": "550e8400-e29b-41d4-a716-446655440002",
  "resource_config": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "name": "Custom High Config",
    "level": "high",
    "data_store_type": "elasticsearch"
  },
  "status": "active",
  "last_rebuild_at": "2024-01-15T10:00:00Z",
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

#### 4.2.2 更新知识库资源绑定

```http
PUT /api/v1/datasets/{dataset_id}/resource-binding
```

**请求体：**

```json
{
  "resource_config_id": "550e8400-e29b-41d4-a716-446655440002",
  "rebuild_index": true  // 是否立即重建索引
}
```

**响应示例：**

```json
{
  "success": true,
  "message": "Resource binding updated",
  "rebuild_task_id": "550e8400-e29b-41d4-a716-446655440005",
  "status": "rebuilding"
}
```

### 4.3 索引重建任务 API

#### 4.3.1 创建重建任务

```http
POST /api/v1/datasets/{dataset_id}/rebuild
```

**请求体：**

```json
{
  "target_config_id": "550e8400-e29b-41d4-a716-446655440002",
  "priority": "normal"  // "low" | "normal" | "high"
}
```

**响应示例：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440005",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440004",
  "source_config_id": "550e8400-e29b-41d4-a716-446655440001",
  "target_config_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  "progress_percent": 0,
  "created_at": "2024-01-15T11:00:00Z"
}
```

#### 4.3.2 获取重建任务状态

```http
GET /api/v1/rebuild-tasks/{task_id}
```

**响应示例：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440005",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440004",
  "status": "running",
  "progress_percent": 45,
  "total_documents": 10000,
  "processed_documents": 4500,
  "started_at": "2024-01-15T11:00:05Z",
  "estimated_completion": "2024-01-15T11:10:00Z"
}
```

#### 4.3.3 取消重建任务

```http
POST /api/v1/rebuild-tasks/{task_id}/cancel
```

**响应示例：**

```json
{
  "success": true,
  "message": "Rebuild task cancelled",
  "status": "cancelled"
}
```

### 4.4 监控 API

#### 4.4.1 获取检索统计

```http
GET /api/v1/monitoring/retrieval-stats
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| dataset_id | string | 否 | 按知识库筛选 |
| start_time | string | 否 | 开始时间（ISO 8601） |
| end_time | string | 否 | 结束时间（ISO 8601） |
| granularity | string | 否 | 粒度：minute/hour/day |

**响应示例：**

```json
{
  "period": {
    "start": "2024-01-15T00:00:00Z",
    "end": "2024-01-15T23:59:59Z"
  },
  "summary": {
    "total_queries": 15000,
    "avg_latency_ms": 85,
    "p50_latency_ms": 60,
    "p95_latency_ms": 200,
    "p99_latency_ms": 500,
    "cache_hit_rate": 0.35
  },
  "by_method": {
    "semantic": {
      "queries": 5000,
      "avg_latency_ms": 120
    },
    "keyword": {
      "queries": 3000,
      "avg_latency_ms": 30
    },
    "hybrid": {
      "queries": 7000,
      "avg_latency_ms": 150
    }
  },
  "by_resource_level": {
    "low": {
      "queries": 2000,
      "avg_latency_ms": 200
    },
    "medium": {
      "queries": 8000,
      "avg_latency_ms": 80
    },
    "high": {
      "queries": 5000,
      "avg_latency_ms": 50
    }
  },
  "time_series": [
    {
      "timestamp": "2024-01-15T00:00:00Z",
      "queries": 100,
      "avg_latency_ms": 90
    }
  ]
}
```

#### 4.4.2 获取存储后端健康状态

```http
GET /api/v1/monitoring/data-store-health
```

**响应示例：**

```json
{
  "checks": [
    {
      "data_store_type": "pgvector",
      "config_id": "550e8400-e29b-41d4-a716-446655440001",
      "status": "healthy",
      "response_time_ms": 5,
      "last_check_at": "2024-01-15T12:00:00Z",
      "details": {
        "version": "15.4",
        "pgvector_version": "0.5.1",
        "connection_pool": {
          "size": 10,
          "available": 8
        }
      }
    },
    {
      "data_store_type": "elasticsearch",
      "config_id": "550e8400-e29b-41d4-a716-446655440002",
      "status": "healthy",
      "response_time_ms": 15,
      "last_check_at": "2024-01-15T12:00:00Z",
      "details": {
        "version": "8.11.0",
        "cluster_status": "green",
        "nodes": 3,
        "shards": 150
      }
    }
  ],
  "overall_status": "healthy"
}
```

#### 4.4.3 获取知识库性能指标

```http
GET /api/v1/datasets/{dataset_id}/metrics
```

**响应示例：**

```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440004",
  "resource_level": "medium",
  "data_store_type": "pgvector",
  "index_stats": {
    "total_documents": 50000,
    "total_chunks": 150000,
    "index_size_mb": 512,
    "last_indexed_at": "2024-01-15T10:00:00Z"
  },
  "retrieval_stats": {
    "total_queries_24h": 5000,
    "avg_latency_ms": 80,
    "p95_latency_ms": 180,
    "error_rate": 0.001
  },
  "storage_stats": {
    "disk_usage_mb": 1024,
    "memory_usage_mb": 256
  }
}
```

### 4.5 扩展 Dify 现有 API

#### 4.5.1 创建知识库（扩展）

```http
POST /api/v1/datasets
```

**新增请求参数：**

```json
{
  "name": "My Knowledge Base",
  "description": "A test knowledge base",
  "indexing_technique": "high_quality",
  "resource_level": "medium",  // 新增：资源级别
  "resource_config_id": null   // 新增：指定配置ID（可选，覆盖默认）
}
```

**响应示例：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440004",
  "name": "My Knowledge Base",
  "description": "A test knowledge base",
  "indexing_technique": "high_quality",
  "resource_level": "medium",
  "resource_config": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "Default Medium Config",
    "data_store_type": "pgvector"
  },
  "created_at": "2024-01-15T09:00:00Z"
}
```

#### 4.5.2 检索知识库（扩展）

```http
POST /api/v1/datasets/{dataset_id}/retrieve
```

**新增响应字段：**

```json
{
  "query": "What is RAG?",
  "results": [
    {
      "content": "RAG (Retrieval-Augmented Generation) is...",
      "score": 0.95,
      "title": "rag_introduction.pdf",
      "metadata": {
        "document_id": "...",
        "page": 1
      }
    }
  ],
  "retrieval_info": {  // 新增：检索信息
    "method": "hybrid",
    "data_store_type": "pgvector",
    "resource_level": "medium",
    "latency_ms": 85,
    "embedding_latency_ms": 45,
    "rerank_latency_ms": 20
  }
}
```

## 5. 错误处理

### 5.1 错误响应格式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      // 可选的额外信息
    },
    "request_id": "req_550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 5.2 错误码列表

| 错误码 | HTTP 状态码 | 说明 |
|--------|------------|------|
| INVALID_REQUEST | 400 | 请求参数无效 |
| INVALID_CONFIG | 400 | 配置无效 |
| CONFIG_IN_USE | 409 | 配置正在使用中 |
| RESOURCE_NOT_FOUND | 404 | 资源不存在 |
| UNAUTHORIZED | 401 | 未授权 |
| FORBIDDEN | 403 | 权限不足 |
| DATA_STORE_ERROR | 500 | 存储后端错误 |
| REBUILD_IN_PROGRESS | 409 | 重建任务进行中 |
| REBUILD_FAILED | 500 | 重建任务失败 |

### 5.3 错误示例

**配置验证错误：**

```json
{
  "error": {
    "code": "INVALID_CONFIG",
    "message": "Configuration validation failed",
    "details": {
      "errors": [
        {
          "field": "config_json.hosts",
          "message": "Must be a non-empty array"
        },
        {
          "field": "config_json.max_documents",
          "message": "Must be greater than 0"
        }
      ]
    },
    "request_id": "req_550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**存储后端连接错误：**

```json
{
  "error": {
    "code": "DATA_STORE_ERROR",
    "message": "Failed to connect to Elasticsearch",
    "details": {
      "data_store_type": "elasticsearch",
      "host": "es01:9200",
      "error": "Connection refused"
    },
    "request_id": "req_550e8400-e29b-41d4-a716-446655440001"
  }
}
```

## 6. 限流策略

### 6.1 限流规则

| 端点 | 限流策略 | 说明 |
|------|---------|------|
| GET /api/v1/resource-configs | 100 req/min | 配置列表查询 |
| POST /api/v1/resource-configs | 10 req/min | 创建配置 |
| POST /api/v1/datasets/{id}/rebuild | 1 req/min | 重建索引 |
| GET /api/v1/monitoring/* | 60 req/min | 监控数据 |

### 6.2 限流响应

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "details": {
      "retry_after": 60
    }
  }
}
```

## 7. 分页规范

### 7.1 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | integer | 1 | 页码 |
| limit | integer | 20 | 每页数量（最大 100） |

### 7.2 响应格式

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

## 8. 版本控制

### 8.1 版本策略

- URL 路径版本：`/api/v1/`
- 向后兼容：v1 保持兼容，新功能在 v2 实现
- 弃用通知：提前 3 个月通知弃用 API

### 8.2 版本协商

```http
GET /api/v1/resource-configs
Accept-Version: v1
```

## 9. WebSocket API（可选）

### 9.1 重建任务进度推送

```javascript
// 连接 WebSocket
const ws = new WebSocket('wss://api.example.com/ws/rebuild-tasks');

// 订阅任务
ws.send(JSON.stringify({
  action: 'subscribe',
  task_id: '550e8400-e29b-41d4-a716-446655440005'
}));

// 接收进度更新
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress_percent}%`);
};
```

### 9.2 实时检索指标

```javascript
// 连接 WebSocket
const ws = new WebSocket('wss://api.example.com/ws/metrics');

// 订阅指标
ws.send(JSON.stringify({
  action: 'subscribe',
  dataset_id: '550e8400-e29b-41d4-a716-446655440004',
  metrics: ['latency', 'qps']
}));

// 接收实时指标
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`QPS: ${data.qps}, Latency: ${data.latency_ms}ms`);
};
```

## 10. 附录

### 10.1 OpenAPI 规范

完整的 OpenAPI 3.0 规范文件位于：`/docs/openapi.yaml`

### 10.2 Postman 集合

Postman 集合文件位于：`/docs/postman-collection.json`

### 10.3 SDK 示例

#### Python

```python
import requests

# 初始化客户端
client = RagPlatformClient(
    base_url="https://api.example.com",
    api_key="your-api-key"
)

# 创建资源配置
config = client.resource_configs.create({
    "name": "High Resource Config",
    "level": "high",
    "data_store_type": "elasticsearch",
    "config_json": {
        "hosts": ["http://es01:9200"],
        "vector_enabled": True
    }
})

# 应用到知识库
client.datasets.apply_resource_config(
    dataset_id="dataset-id",
    config_id=config.id,
    rebuild_index=True
)
```

#### JavaScript

```javascript
import { RagPlatformClient } from '@rag-platform/sdk';

const client = new RagPlatformClient({
  baseUrl: 'https://api.example.com',
  apiKey: 'your-api-key'
});

// 获取监控数据
const stats = await client.monitoring.getRetrievalStats({
  datasetId: 'dataset-id',
  granularity: 'hour'
});

console.log(`Average latency: ${stats.summary.avg_latency_ms}ms`);
```
