# 实施规范 (SPEC)

## 1. 项目信息

- **项目名称**: RAG 私有化专业知识问答平台
- **项目代号**: rag-platform
- **版本**: v1.0.0
- **状态**: 规划中

## 2. 技术规范

### 2.1 后端规范

#### Python 代码规范
- **格式化**: Black (line-length: 100)
- **类型检查**: MyPy (strict mode)
- **代码风格**: PEP 8
- **文档字符串**: Google Style

#### 项目结构
```
api/
├── core/
│   ├── rag/
│   │   ├── datasource/
│   │   │   ├── unified/          # 统一数据层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_data_store.py
│   │   │   │   ├── data_store_factory.py
│   │   │   │   ├── sqlite_data_store.py
│   │   │   │   ├── pgvector_data_store.py
│   │   │   │   ├── elasticsearch_data_store.py
│   │   │   │   └── exceptions.py
│   │   │   ├── vdb/              # Dify 向量数据库适配器
│   │   │   └── keyword/          # Dify 关键词检索适配器
│   │   ├── retrieval/            # 增强检索引擎
│   │   │   ├── __init__.py
│   │   │   ├── multi_way_retriever.py
│   │   │   ├── fusion_strategies.py
│   │   │   └── reranker.py
│   │   └── models/               # 数据模型
│   ├── services/                 # 业务服务
│   │   ├── resource_config_service.py
│   │   └── monitoring_service.py
│   └── configs/                  # 配置管理
│       └── resource_config.py
├── models/                       # 数据库模型
│   ├── resource_config.py
│   ├── dataset_resource_binding.py
│   ├── retrieval_metric.py
│   └── index_rebuild_task.py
├── api/                          # API 路由
│   ├── resource_configs.py
│   ├── datasets.py
│   └── monitoring.py
└── tests/                        # 测试
    ├── unit/
    ├── integration/
    └── performance/
```

#### API 规范
- **框架**: Flask/FastAPI
- **序列化**: Pydantic v2
- **文档**: OpenAPI 3.0 + Swagger UI
- **版本**: URL 路径版本 `/api/v1/`

### 2.2 前端规范

#### TypeScript 代码规范
- **类型检查**: TypeScript (strict mode)
- **代码风格**: ESLint + Prettier
- **组件**: 函数组件 + Hooks

#### 项目结构
```
web/
├── app/                          # Next.js App Router
│   ├── (dashboard)/
│   │   ├── resource-configs/
│   │   │   ├── page.tsx
│   │   │   ├── new/
│   │   │   └── [id]/
│   │   ├── datasets/
│   │   └── monitoring/
│   ├── api/                      # API Routes
│   └── layout.tsx
├── components/
│   ├── ui/                       # shadcn/ui 组件
│   ├── resource-config/          # 资源配置组件
│   ├── monitoring/               # 监控组件
│   └── common/                   # 通用组件
├── hooks/                        # 自定义 Hooks
├── lib/                          # 工具函数
├── types/                        # TypeScript 类型
└── styles/                       # 全局样式
```

### 2.3 数据库规范

#### 命名规范
- **表名**: 小写，下划线分隔，复数形式
- **字段名**: 小写，下划线分隔
- **索引名**: `idx_表名_字段名`
- **外键名**: `fk_表名_引用表`

#### 字段规范
- **主键**: UUID，默认 `gen_random_uuid()`
- **时间戳**: `created_at`, `updated_at`
- **软删除**: `is_active` 或 `deleted_at`
- **租户隔离**: 所有表包含 `tenant_id`

### 2.4 测试规范

#### 单元测试
- **框架**: pytest (后端), Jest (前端)
- **覆盖率**: > 80%
- **Mock**: pytest-mock, MSW

#### 集成测试
- **框架**: pytest + TestClient
- **数据库**: 独立测试数据库
- **外部服务**: Docker Compose 启动

#### 性能测试
- **工具**: Locust (后端), Lighthouse (前端)
- **基准**: 定义在 `docs/performance-baseline.md`

## 3. 开发流程

### 3.1 Git 工作流

```
main (生产分支)
  │
  ├──→ develop (开发分支)
  │       │
  │       ├──→ feature/resource-config (功能分支)
  │       │       │
  │       │       └──→ PR → Code Review → Merge
  │       │
  │       ├──→ feature/sqlite-adapter
  │       │
  │       └──→ release/v1.0.0 (发布分支)
  │               │
  │               └──→ Tag v1.0.0 → Merge to main
  │
  └──→ hotfix/v1.0.1 (热修复分支)
          │
          └──→ Tag v1.0.1 → Merge to main & develop
```

### 3.2 提交规范

#### Conventional Commits

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

#### 类型说明

| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 |
| docs | 文档 |
| style | 格式（不影响代码运行）|
| refactor | 重构 |
| perf | 性能优化 |
| test | 测试 |
| chore | 构建过程或辅助工具的变动 |

#### 示例

```bash
feat(resource-config): add CRUD API for resource configs

- Implement ResourceConfigService
- Add REST API endpoints
- Add validation logic

Closes #123
```

### 3.3 代码审查

#### 审查清单

- [ ] 功能正确性
- [ ] 代码风格合规
- [ ] 单元测试覆盖
- [ ] 文档更新
- [ ] 性能影响
- [ ] 安全考虑

#### 审查流程

1. 提交 PR
2. 自动化检查（CI）
3. 至少 1 人审查
4. 解决评论
5. 合并代码

## 4. 部署规范

### 4.1 环境定义

| 环境 | 用途 | 部署方式 |
|------|------|----------|
| local | 本地开发 | Docker Compose |
| dev | 开发测试 | Docker Compose |
| staging | 预发布 | Docker Swarm/K8s |
| prod | 生产 | Docker Swarm/K8s |

### 4.2 部署流程

```bash
# 1. 构建镜像
docker build -t rag-platform:v1.0.0 .

# 2. 推送镜像
docker push rag-platform:v1.0.0

# 3. 部署服务
docker-compose -f docker-compose.prod.yml up -d

# 4. 健康检查
curl http://localhost:5001/health

# 5. 监控验证
# 检查 Grafana 仪表板
```

### 4.3 回滚流程

```bash
# 1. 回滚到上一版本
docker-compose -f docker-compose.prod.yml pull rag-platform:v0.9.0
docker-compose -f docker-compose.prod.yml up -d

# 2. 验证服务
# 检查健康检查端点

# 3. 监控验证
# 检查错误率是否恢复
```

## 5. 监控规范

### 5.1 关键指标

| 指标 | 类型 | 告警阈值 |
|------|------|----------|
| retrieval_latency_ms | Histogram | P95 > 500ms |
| retrieval_qps | Counter | - |
| data_store_health | Gauge | 0 (unhealthy) |
| error_rate | Gauge | > 1% |

### 5.2 日志规范

#### 日志格式

```json
{
  "timestamp": "2024-01-15T12:00:00Z",
  "level": "INFO",
  "logger": "resource_config_service",
  "message": "Resource config created",
  "context": {
    "config_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
    "level": "medium"
  },
  "request_id": "req_550e8400-e29b-41d4-a716-446655440000"
}
```

#### 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 开发调试 |
| INFO | 正常流程 |
| WARNING | 警告（可恢复）|
| ERROR | 错误（需处理）|
| CRITICAL | 严重错误（立即处理）|

## 6. 安全规范

### 6.1 认证授权
- 复用 Dify 认证体系
- API Key 管理
- JWT Token 过期策略

### 6.2 数据安全
- 敏感配置加密存储
- 数据库连接 SSL
- 备份加密

### 6.3 代码安全
- 依赖漏洞扫描
- 代码安全审查
- Secret 检测

## 7. 文档规范

### 7.1 代码文档
- 公共 API 必须有 docstring
- 复杂逻辑必须有注释
- 类型注解必须完整

### 7.2 技术文档
- 架构变更必须更新架构文档
- API 变更必须更新 API 文档
- 部署变更必须更新部署文档

### 7.3 用户文档
- 新功能必须有用户手册
- 界面变更必须更新截图
- 常见问题必须更新 FAQ

## 8. 附录

### 8.1 环境变量清单

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| DATA_STORE_TYPE | 数据存储类型 | pgvector | 是 |
| SQLITE_DB_PATH | SQLite 数据库路径 | data/rag.db | 条件 |
| PGVECTOR_HOST | PostgreSQL 主机 | localhost | 条件 |
| PGVECTOR_PORT | PostgreSQL 端口 | 5432 | 条件 |
| ELASTICSEARCH_HOSTS | ES 节点地址 | http://localhost:9200 | 条件 |
| RESOURCE_LEVEL | 默认资源级别 | medium | 否 |
| LOG_LEVEL | 日志级别 | INFO | 否 |

### 8.2 常用命令

```bash
# 启动开发环境
docker-compose up -d

# 运行测试
pytest

# 代码格式化
black api/

# 类型检查
mypy api/

# 构建镜像
docker build -t rag-platform:latest .

# 查看日志
docker-compose logs -f api
```

### 8.3 参考资源

- [Dify 文档](https://docs.dify.ai)
- [pgvector 文档](https://github.com/pgvector/pgvector)
- [Elasticsearch 文档](https://www.elastic.co/guide/index.html)
- [Conventional Commits](https://www.conventionalcommits.org)
