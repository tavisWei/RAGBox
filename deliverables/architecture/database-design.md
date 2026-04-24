# 数据库设计文档

## 1. 概述

本文档描述 RAG 私有化专业知识问答平台的数据库设计，包括新增表结构和与 Dify 现有表的关联关系。

## 2. 设计原则

- **最小侵入**：不修改 Dify 现有表结构，只新增扩展表
- **外键关联**：通过外键与 Dify 现有表关联，保持数据一致性
- **JSONB 灵活存储**：配置信息使用 JSONB，便于扩展
- **租户隔离**：所有新增表包含 `tenant_id` 字段，支持多租户

## 3. 新增表结构

### 3.1 resource_configs（资源配置表）

存储系统级和租户级的资源配置信息。

```sql
CREATE TABLE resource_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level VARCHAR(20) NOT NULL CHECK (level IN ('low', 'medium', 'high')),
    data_store_type VARCHAR(50) NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_by UUID,
    
    -- 唯一约束：每个租户只有一个默认配置
    CONSTRAINT uq_tenant_default UNIQUE (tenant_id, is_default)
        DEFERRABLE INITIALLY DEFERRED
);

-- 索引
CREATE INDEX idx_resource_configs_tenant ON resource_configs(tenant_id);
CREATE INDEX idx_resource_configs_level ON resource_configs(level);
CREATE INDEX idx_resource_configs_active ON resource_configs(is_active);

-- 注释
COMMENT ON TABLE resource_configs IS '资源配置表，存储高中低三种资源级别的配置';
COMMENT ON COLUMN resource_configs.level IS '资源级别：low-低资源, medium-中资源, high-高资源';
COMMENT ON COLUMN resource_configs.data_store_type IS '数据存储后端类型：sqlite, pgvector, elasticsearch';
COMMENT ON COLUMN resource_configs.config_json IS '详细配置JSON，包含连接参数、检索策略等';
```

**配置 JSON 示例：**

```json
{
  "low": {
    "data_store_type": "sqlite",
    "db_path": "data/rag.db",
    "vector_enabled": false,
    "keyword_enabled": true,
    "fulltext_enabled": true,
    "hybrid_fusion_method": "rrf",
    "rerank_enabled": false,
    "max_documents": 10000,
    "embedding_model": "text-embedding-3-small",
    "chunk_size": 500,
    "chunk_overlap": 50
  },
  "medium": {
    "data_store_type": "pgvector",
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
  "high": {
    "data_store_type": "elasticsearch",
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
  }
}
```

### 3.2 dataset_resource_bindings（知识库资源绑定表）

关联知识库与资源配置，支持知识库级别的资源级别覆盖。

```sql
CREATE TABLE dataset_resource_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL,
    resource_config_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'rebuilding', 'error', 'deprecated')),
    last_rebuild_at TIMESTAMP WITH TIME ZONE,
    rebuild_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_dataset 
        FOREIGN KEY (dataset_id) 
        REFERENCES datasets(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_resource_config 
        FOREIGN KEY (resource_config_id) 
        REFERENCES resource_configs(id) 
        ON DELETE RESTRICT,
    
    -- 唯一约束：每个知识库只有一个活跃绑定
    CONSTRAINT uq_dataset_active UNIQUE (dataset_id)
);

-- 索引
CREATE INDEX idx_dataset_bindings_dataset ON dataset_resource_bindings(dataset_id);
CREATE INDEX idx_dataset_bindings_config ON dataset_resource_bindings(resource_config_id);
CREATE INDEX idx_dataset_bindings_status ON dataset_resource_bindings(status);

-- 注释
COMMENT ON TABLE dataset_resource_bindings IS '知识库与资源配置的绑定关系';
COMMENT ON COLUMN dataset_resource_bindings.status IS '绑定状态：active-活跃, rebuilding-重建中, error-错误, deprecated-已废弃';
```

### 3.3 retrieval_metrics（检索性能指标表）

记录检索性能指标，用于监控和优化。

```sql
CREATE TABLE retrieval_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    dataset_id UUID,
    query_hash VARCHAR(64),
    query_text TEXT,
    retrieval_method VARCHAR(50) NOT NULL,
    data_store_type VARCHAR(50) NOT NULL,
    resource_level VARCHAR(20) NOT NULL,
    query_latency_ms INTEGER NOT NULL,
    embedding_latency_ms INTEGER,
    rerank_latency_ms INTEGER,
    result_count INTEGER NOT NULL DEFAULT 0,
    score_threshold FLOAT,
    top_k INTEGER,
    is_hit BOOLEAN,
    user_feedback INTEGER,  -- 1: thumbs up, -1: thumbs down, NULL: no feedback
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_metrics_dataset 
        FOREIGN KEY (dataset_id) 
        REFERENCES datasets(id) 
        ON DELETE SET NULL
);

-- 索引
CREATE INDEX idx_retrieval_metrics_tenant ON retrieval_metrics(tenant_id);
CREATE INDEX idx_retrieval_metrics_dataset ON retrieval_metrics(dataset_id);
CREATE INDEX idx_retrieval_metrics_created ON retrieval_metrics(created_at);
CREATE INDEX idx_retrieval_metrics_method ON retrieval_metrics(retrieval_method);

-- 分区（按月分区，保留90天）
-- CREATE TABLE retrieval_metrics_y2024m01 PARTITION OF retrieval_metrics
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- 注释
COMMENT ON TABLE retrieval_metrics IS '检索性能指标表，用于监控和优化检索性能';
COMMENT ON COLUMN retrieval_metrics.query_hash IS '查询文本的哈希值，用于去重和缓存';
COMMENT ON COLUMN retrieval_metrics.is_hit IS '是否命中缓存';
```

### 3.4 data_store_health_checks（存储后端健康检查表）

记录各存储后端的健康检查状态。

```sql
CREATE TABLE data_store_health_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    data_store_type VARCHAR(50) NOT NULL,
    config_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'unknown' 
        CHECK (status IN ('healthy', 'unhealthy', 'unknown', 'degraded')),
    response_time_ms INTEGER,
    error_message TEXT,
    last_check_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_health_config 
        FOREIGN KEY (config_id) 
        REFERENCES resource_configs(id) 
        ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_health_checks_tenant ON data_store_health_checks(tenant_id);
CREATE INDEX idx_health_checks_store ON data_store_health_checks(data_store_type);
CREATE INDEX idx_health_checks_status ON data_store_health_checks(status);
CREATE INDEX idx_health_checks_time ON data_store_health_checks(last_check_at);

-- 注释
COMMENT ON TABLE data_store_health_checks IS '存储后端健康检查记录';
```

### 3.5 index_rebuild_tasks（索引重建任务表）

记录索引重建任务，支持异步重建和进度跟踪。

```sql
CREATE TABLE index_rebuild_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    source_config_id UUID NOT NULL,
    target_config_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    progress_percent INTEGER DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
    total_documents INTEGER,
    processed_documents INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    
    -- 外键约束
    CONSTRAINT fk_rebuild_dataset 
        FOREIGN KEY (dataset_id) 
        REFERENCES datasets(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_rebuild_source 
        FOREIGN KEY (source_config_id) 
        REFERENCES resource_configs(id) 
        ON DELETE RESTRICT,
    CONSTRAINT fk_rebuild_target 
        FOREIGN KEY (target_config_id) 
        REFERENCES resource_configs(id) 
        ON DELETE RESTRICT
);

-- 索引
CREATE INDEX idx_rebuild_tasks_tenant ON index_rebuild_tasks(tenant_id);
CREATE INDEX idx_rebuild_tasks_dataset ON index_rebuild_tasks(dataset_id);
CREATE INDEX idx_rebuild_tasks_status ON index_rebuild_tasks(status);

-- 注释
COMMENT ON TABLE index_rebuild_tasks IS '索引重建任务表，支持异步重建和进度跟踪';
```

## 4. 与 Dify 现有表的关联

### 4.1 关联关系图

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
│   tenants       │────▶│   resource_configs       │◀────│ dataset_resource│
│  (Dify 现有)    │     │   (新增)                  │     │ _bindings       │
└─────────────────┘     └──────────────────────────┘     │   (新增)        │
                                                         └─────────────────┘
                                                                  │
                                                                  ▼
                                                         ┌─────────────────┐
                                                         │    datasets     │
                                                         │  (Dify 现有)    │
                                                         └─────────────────┘
                                                                  │
                                                                  ▼
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
│   tenants       │────▶│   retrieval_metrics      │────▶│    datasets     │
│  (Dify 现有)    │     │   (新增)                  │     │  (Dify 现有)    │
└─────────────────┘     └──────────────────────────┘     └─────────────────┘
```

### 4.2 关联说明

| 新增表 | 关联 Dify 表 | 关联类型 | 说明 |
|--------|-------------|----------|------|
| resource_configs | tenants | 多对一 | 配置属于某个租户 |
| dataset_resource_bindings | datasets | 一对一 | 知识库绑定一个资源配置 |
| dataset_resource_bindings | resource_configs | 多对一 | 绑定引用资源配置 |
| retrieval_metrics | datasets | 多对一 | 指标记录属于某个知识库 |
| index_rebuild_tasks | datasets | 多对一 | 重建任务针对某个知识库 |

## 5. 数据迁移策略

### 5.1 从现有 Dify 迁移

```sql
-- 1. 创建默认资源配置（中等级别）
INSERT INTO resource_configs (tenant_id, name, level, data_store_type, config_json, is_default)
SELECT 
    id as tenant_id,
    'Default Medium Config' as name,
    'medium' as level,
    'pgvector' as data_store_type,
    '{
        "host": "localhost",
        "port": 5432,
        "database": "dify",
        "vector_enabled": true,
        "keyword_enabled": true,
        "fulltext_enabled": true,
        "hybrid_fusion_method": "rrf",
        "rerank_enabled": true
    }'::jsonb as config_json,
    true as is_default
FROM tenants;

-- 2. 为现有知识库创建绑定
INSERT INTO dataset_resource_bindings (dataset_id, resource_config_id, status)
SELECT 
    d.id as dataset_id,
    rc.id as resource_config_id,
    'active' as status
FROM datasets d
JOIN resource_configs rc ON d.tenant_id = rc.tenant_id AND rc.is_default = true;
```

### 5.2 版本升级迁移

```sql
-- 版本 0.1.0 → 0.2.0
-- 添加新字段示例
ALTER TABLE resource_configs 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 创建新索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_configs_active 
ON resource_configs(is_active);
```

## 6. 性能优化

### 6.1 索引策略

| 表 | 索引字段 | 索引类型 | 说明 |
|----|---------|---------|------|
| resource_configs | tenant_id + is_default | 唯一索引 | 快速查找租户默认配置 |
| dataset_resource_bindings | dataset_id | 唯一索引 | 快速查找知识库绑定 |
| retrieval_metrics | created_at | B-tree | 时间范围查询 |
| retrieval_metrics | tenant_id + created_at | 复合索引 | 租户级时间查询 |

### 6.2 分区策略

**retrieval_metrics 表按月分区：**

```sql
-- 创建分区表
CREATE TABLE retrieval_metrics (
    id UUID,
    tenant_id UUID,
    dataset_id UUID,
    query_hash VARCHAR(64),
    query_text TEXT,
    retrieval_method VARCHAR(50),
    data_store_type VARCHAR(50),
    resource_level VARCHAR(20),
    query_latency_ms INTEGER,
    result_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 创建分区
CREATE TABLE retrieval_metrics_y2024m01 PARTITION OF retrieval_metrics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE retrieval_metrics_y2024m02 PARTITION OF retrieval_metrics
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- 自动创建未来分区（使用 pg_partman 扩展）
```

### 6.3 清理策略

```sql
-- 定期清理过期指标（保留90天）
DELETE FROM retrieval_metrics 
WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';

-- 清理已完成且过期的重建任务
DELETE FROM index_rebuild_tasks 
WHERE status = 'completed' 
AND completed_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
```

## 7. 备份与恢复

### 7.1 备份策略

| 数据类型 | 备份频率 | 保留周期 | 方式 |
|----------|---------|---------|------|
| 配置数据 | 实时 | 永久 | 数据库主从复制 |
| 指标数据 | 每日 | 90天 | 分区归档 |
| 任务数据 | 每日 | 30天 | 逻辑备份 |

### 7.2 恢复流程

1. **配置恢复**
   ```bash
   pg_restore --table=resource_configs backup.sql
   ```

2. **完整恢复**
   ```bash
   pg_restore --clean --if-exists full_backup.sql
   ```

## 8. 安全设计

### 8.1 数据加密

- **传输加密**：PostgreSQL SSL/TLS
- **存储加密**：透明数据加密（TDE）
- **敏感字段**：配置中的密码使用 AES-256 加密存储

### 8.2 访问控制

```sql
-- 创建只读角色
CREATE ROLE rag_readonly;
GRANT SELECT ON resource_configs TO rag_readonly;
GRANT SELECT ON dataset_resource_bindings TO rag_readonly;

-- 创建读写角色
CREATE ROLE rag_readwrite;
GRANT SELECT, INSERT, UPDATE ON resource_configs TO rag_readwrite;
GRANT SELECT, INSERT, UPDATE ON dataset_resource_bindings TO rag_readwrite;
```

## 9. 附录

### 9.1 完整 ER 图

```
┌─────────────────────┐
│     tenants         │
├─────────────────────┤
│ id (PK)             │
│ name                │
│ ...                 │
└──────────┬──────────┘
           │
           │ 1:N
           ▼
┌─────────────────────┐       ┌─────────────────────┐
│  resource_configs   │◀──────│dataset_resource_    │
├─────────────────────┤  1:1  │bindings             │
│ id (PK)             │       ├─────────────────────┤
│ tenant_id (FK)      │       │ id (PK)             │
│ name                │       │ dataset_id (FK)     │
│ level               │       │ resource_config_id  │
│ data_store_type     │       │ status              │
│ config_json         │       │ last_rebuild_at     │
│ is_default          │       └──────────┬──────────┘
│ is_active           │                  │
└─────────────────────┘                  │ N:1
                                         ▼
                              ┌─────────────────────┐
                              │      datasets       │
                              │  (Dify 现有)        │
                              └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│  retrieval_metrics  │──────▶│      datasets       │
├─────────────────────┤  N:1  │  (Dify 现有)        │
│ id (PK)             │       └─────────────────────┘
│ tenant_id           │
│ dataset_id (FK)     │
│ query_hash          │
│ query_text          │
│ retrieval_method    │
│ query_latency_ms    │
│ result_count        │
│ created_at          │
└─────────────────────┘

┌─────────────────────┐
│ index_rebuild_tasks │
├─────────────────────┤
│ id (PK)             │
│ tenant_id           │
│ dataset_id (FK)     │
│ source_config_id    │
│ target_config_id    │
│ status              │
│ progress_percent    │
│ created_at          │
└─────────────────────┘
```

### 9.2 命名规范

| 对象类型 | 命名规范 | 示例 |
|----------|---------|------|
| 表名 | 小写，下划线分隔 | `resource_configs` |
| 字段名 | 小写，下划线分隔 | `data_store_type` |
| 索引名 | `idx_表名_字段名` | `idx_resource_configs_tenant` |
| 外键名 | `fk_表名_引用表` | `fk_dataset_bindings_config` |
| 约束名 | `uq_表名_字段名` | `uq_tenant_default` |
