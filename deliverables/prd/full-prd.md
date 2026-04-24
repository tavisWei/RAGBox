# RAG 私有化专业知识问答平台 - 产品需求文档 (PRD)

## 1. 项目概述

### 1.1 项目背景
基于 Dify 开源平台二次开发，构建支持高中低三种资源适配的私有化专业知识问答平台。平台通过统一的数据层抽象，允许用户根据实际资源条件（硬件、数据量、并发需求）灵活选择最适合的 RAG 检索方案，无需修改代码即可在轻量级单机部署和企业级分布式部署之间切换。

### 1.2 核心目标
- **资源自适应**：支持低/中/高三种资源级别，自动选择最优检索后端
- **数据层统一**：抽象统一接口，支持 SQLite、PostgreSQL、Elasticsearch 等多种存储后端
- **Dify 深度集成**：保持与 Dify 现有功能完全兼容，通过扩展点和插件机制增强能力
- **私有化部署**：完整支持离线环境，无外部依赖

### 1.3 目标用户
- **个人开发者/研究者**：低资源方案，单机运行，快速验证
- **中小企业**：中资源方案，部门级应用，自托管可控
- **大型企业/机构**：高资源方案，大规模数据，高可用集群

---

## 2. 技术调研结论

### 2.1 RAG 检索方案对比

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| 纯向量检索 | 语义理解强 | 精确匹配差 | 概念性查询 |
| 纯倒排索引(BM25) | 精确匹配强、速度快 | 无语义理解 | 术语/ID搜索 |
| **混合检索(推荐)** | 兼具两者优势 | 复杂度增加 | **生产环境** |

### 2.2 Dify 现有架构分析

**Dify RAG 核心组件：**
- `BaseVector` 抽象基类：支持 37+ 种向量数据库
- `BaseKeyword` 抽象基类：支持 jieba 关键词检索
- `RetrievalService`：统一检索调度，支持并行检索
- 四种检索模式：`SEMANTIC_SEARCH`、`FULL_TEXT_SEARCH`、`HYBRID_SEARCH`、`KEYWORD_SEARCH`

**Dify 扩展点：**
- 向量后端插件（`dify.vector_backends` entry point）
- 外部知识库 API（标准 REST 接口）
- 数据源插件（自定义文档处理）

### 2.3 高中低资源方案定义

| 级别 | 数据规模 | 并发 | 存储方案 | 检索方案 |
|------|----------|------|----------|----------|
| **低** | < 1万文档 | < 10 | SQLite + FTS5 | 关键词/BM25 + 可选向量 |
| **中** | 1万-100万 | < 1000 | PostgreSQL + pgvector | 混合检索（BM25 + 向量） |
| **高** | > 100万 | > 1000 | ES/Milvus 集群 | 多路召回 + 重排序 |

---

## 3. 功能需求

### 3.1 核心功能模块

#### 3.1.1 资源适配配置中心
- **资源级别设置**：系统级默认资源级别配置
- **知识库级别覆盖**：创建知识库时可选择覆盖系统默认级别
- **动态切换**：支持运行时切换资源级别（需重建索引）
- **配置持久化**：存储于数据库，支持导入导出

#### 3.1.2 统一数据层（Unified Data Layer）
- **后端适配器接口**：`BaseDataStore` 抽象基类
- **内置适配器**：
  - `SQLiteDataStore`：低资源方案，FTS5 + 可选向量
  - `PGVectorDataStore`：中资源方案，pgvector + tsvector
  - `ElasticsearchDataStore`：高资源方案，ES 原生混合检索
- **自动后端选择**：根据资源级别自动初始化对应适配器

#### 3.1.3 增强检索引擎
- **多路召回**：向量 + 关键词 + 全文，并行执行
- **融合策略**：RRF（Reciprocal Rank Fusion）、加权融合
- **重排序支持**：集成 BGE Reranker、Cohere Rerank
- **查询路由**：根据查询类型自动选择最优检索策略

#### 3.1.4 知识库管理增强
- **资源级别标签**：知识库列表显示当前资源级别
- **索引重建**：支持切换资源级别后重建索引
- **性能监控**：显示索引大小、查询延迟、命中率

#### 3.1.5 系统监控面板
- **资源使用监控**：CPU、内存、磁盘、数据库连接数
- **检索性能指标**：QPS、延迟 P50/P95/P99、召回率
- **后端状态**：各存储后端健康状态

### 3.2 用户角色与权限

| 角色 | 权限 |
|------|------|
| 系统管理员 | 配置资源级别、管理系统设置、查看监控 |
| 知识库管理员 | 创建/管理知识库、选择资源级别、上传文档 |
| 普通用户 | 使用问答功能、查看知识库列表 |

---

## 4. 非功能需求

### 4.1 性能要求
- **低资源**：查询延迟 < 500ms（含 embedding 生成）
- **中资源**：查询延迟 < 200ms
- **高资源**：查询延迟 < 100ms

### 4.2 兼容性要求
- **向后兼容**：现有 Dify API 完全兼容，不破坏现有客户端
- **数据兼容**：现有知识库数据可无缝迁移
- **配置兼容**：支持从现有 Dify 配置平滑升级

### 4.3 可用性要求
- **功能开关**：新功能通过 Feature Flag 控制，可灰度发布
- **降级策略**：高资源方案组件故障时可降级至中/低资源方案
- **健康检查**：各存储后端独立健康检查

---

## 5. 技术架构

### 5.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Dify Frontend (React)                    │
│              + 资源适配配置页面 + 监控面板                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│              Dify API Layer (Flask/FastAPI)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Resource   │  │   Unified   │  │    Enhanced         │  │
│  │  Config     │  │   Data      │  │    Retrieval        │  │
│  │  Service    │  │   Layer     │  │    Engine           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│              Backend Adapter Layer (Pluggable)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  SQLite  │ │PGVector  │ │   ES     │ │   External   │  │
│  │  + FTS5  │ │+tsvector │ │  Cluster │ │    API       │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 核心组件设计

#### 5.2.1 BaseDataStore 抽象接口

```python
class BaseDataStore(ABC):
    """统一数据层抽象基类"""
    
    @abstractmethod
    def create_collection(self, name: str, schema: dict) -> None:
        """创建集合/表/索引"""
        pass
    
    @abstractmethod
    def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> None:
        """添加文档（可选向量）"""
        pass
    
    @abstractmethod
    def search(self, query: str, query_vector: list[float] | None = None, 
               top_k: int = 10, filters: dict | None = None) -> list[SearchResult]:
        """统一检索接口"""
        pass
    
    @abstractmethod
    def delete_documents(self, doc_ids: list[str]) -> None:
        pass
    
    @abstractmethod
    def get_stats(self) -> DataStoreStats:
        """获取存储统计信息"""
        pass
```

#### 5.2.2 资源级别配置模型

```python
class ResourceLevel(Enum):
    LOW = "low"      # SQLite + FTS5
    MEDIUM = "medium" # PostgreSQL + pgvector
    HIGH = "high"    # Elasticsearch/Milvus

class ResourceConfig(BaseModel):
    level: ResourceLevel
    data_store_type: str
    vector_enabled: bool
    keyword_enabled: bool
    fulltext_enabled: bool
    hybrid_fusion_method: str  # "rrf" | "weighted"
    rerank_enabled: bool
    max_documents: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
```

### 5.3 数据流

#### 5.3.1 文档索引流程
```
文档上传 → 格式解析 → 文本分块 → 资源级别判断 → 选择后端 → 生成 Embedding（可选） → 写入存储 → 更新索引
```

#### 5.3.2 查询检索流程
```
用户查询 → 查询分析 → 资源级别判断 → 选择检索策略 → 并行检索（向量+关键词+全文） → 结果融合 → 重排序（可选） → 返回结果
```

---

## 6. 数据库设计

### 6.1 新增表结构

#### resource_configs（资源配置表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| tenant_id | UUID | 租户ID |
| level | VARCHAR(20) | 资源级别：low/medium/high |
| data_store_type | VARCHAR(50) | 存储后端类型 |
| config_json | JSONB | 详细配置JSON |
| is_default | BOOLEAN | 是否为默认配置 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### dataset_resource_bindings（知识库资源绑定表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| dataset_id | UUID | 知识库ID |
| resource_config_id | UUID | 资源配置ID |
| status | VARCHAR(20) | 状态：active/rebuilding/error |
| last_rebuild_at | TIMESTAMP | 上次重建时间 |

#### retrieval_metrics（检索指标表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| dataset_id | UUID | 知识库ID |
| query_latency_ms | INTEGER | 查询延迟 |
| result_count | INTEGER | 返回结果数 |
| retrieval_method | VARCHAR(50) | 检索方法 |
| created_at | TIMESTAMP | 记录时间 |

---

## 7. API 设计

### 7.1 资源配置 API

#### GET /api/resource-configs
获取资源配置列表

#### POST /api/resource-configs
创建资源配置

#### PUT /api/resource-configs/{id}
更新资源配置

#### POST /api/resource-configs/{id}/apply
应用配置到系统/知识库

### 7.2 监控 API

#### GET /api/monitoring/retrieval-stats
获取检索统计

#### GET /api/monitoring/data-store-health
获取存储后端健康状态

### 7.3 扩展 Dify 现有 API

#### POST /api/datasets（扩展）
创建知识库时增加 `resource_level` 参数

#### GET /api/datasets/{id}/retrieval（扩展）
检索结果增加 `retrieval_backend` 和 `latency_ms` 字段

---

## 8. 前端设计

### 8.1 新增页面

#### 8.1.1 资源适配配置页
- 系统级默认配置设置
- 三种资源级别卡片展示
- 配置参数表单（数据库连接、模型选择等）
- 测试连接按钮

#### 8.1.2 知识库创建向导（增强）
- Step 1: 基本信息（名称、描述）
- Step 2: 资源级别选择（继承系统默认或自定义）
- Step 3: 文档上传
- Step 4: 索引确认

#### 8.1.3 系统监控面板
- 实时 QPS/延迟图表
- 存储后端状态卡片
- 知识库资源分布饼图
- 检索方法使用趋势

### 8.2 组件规范
- 使用 Dify 现有设计系统（shadcn/ui + Tailwind）
- 资源级别使用颜色区分：低(绿色)、中(蓝色)、高(紫色)
- 状态标签：运行中(绿色)、重建中(黄色)、错误(红色)

---

## 9. 实施计划

### Phase 1: 基础架构（Week 1-2）
- [ ] 创建 `BaseDataStore` 抽象接口
- [ ] 实现 `SQLiteDataStore` 适配器
- [ ] 实现资源配置数据库模型
- [ ] 配置管理服务 API

### Phase 2: 核心功能（Week 3-4）
- [ ] 实现 `PGVectorDataStore` 适配器
- [ ] 实现 `ElasticsearchDataStore` 适配器
- [ ] 增强检索引擎（多路召回+融合）
- [ ] 集成 Dify 检索流程

### Phase 3: 前端集成（Week 5-6）
- [ ] 资源适配配置页面
- [ ] 知识库创建向导增强
- [ ] 系统监控面板
- [ ] 前端与后端联调

### Phase 4: 测试优化（Week 7-8）
- [ ] 单元测试覆盖
- [ ] 集成测试（三种资源级别）
- [ ] 性能基准测试
- [ ] 文档编写

---

## 10. 验收标准

### 10.1 功能验收
- [ ] 低资源方案：单机 SQLite 运行，支持 1000 文档，查询 < 500ms
- [ ] 中资源方案：PostgreSQL + pgvector，支持 10万 文档，查询 < 200ms
- [ ] 高资源方案：ES 集群，支持 100万+ 文档，查询 < 100ms
- [ ] 配置切换：修改资源级别后，新知识库自动使用新配置
- [ ] 向后兼容：现有 Dify 功能不受影响

### 10.2 性能验收
- [ ] 索引构建速度：低资源 < 1min/1000文档，中资源 < 30min/10万文档
- [ ] 并发支持：低资源 10 QPS，中资源 1000 QPS，高资源 10000 QPS
- [ ] 内存占用：低资源 < 512MB，中资源 < 4GB，高资源 按需扩展

### 10.3 质量验收
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试覆盖三种资源级别
- [ ] 文档完整（API 文档、部署指南、用户手册）

---

## 11. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Dify 版本升级冲突 | 高 | 保持模块化设计，最小化对 Dify 核心代码的修改 |
| 混合检索效果不佳 | 中 | 提供调参接口，支持 A/B 测试不同融合策略 |
| 数据迁移复杂 | 中 | 提供自动迁移脚本，支持增量迁移 |
| 性能不达预期 | 中 | 提前进行 PoC 验证，预留优化时间 |

---

## 12. 附录

### 12.1 参考资源
- [Dify GitHub](https://github.com/langgenius/dify)
- [Dify External Knowledge API](https://docs.dify.ai/en/use-dify/knowledge/external-knowledge-api)
- [Elasticsearch Hybrid Search](https://www.elastic.co/elasticsearch/hybrid-search)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [RRF Paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

### 12.2 术语表
- **RAG**: Retrieval-Augmented Generation，检索增强生成
- **BM25**: Best Match 25，经典文本检索排序算法
- **RRF**: Reciprocal Rank Fusion，倒数排名融合
- **HNSW**: Hierarchical Navigable Small World，向量索引算法
- **Embedding**: 文本向量化表示
