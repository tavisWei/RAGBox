# RAG 私有化专业知识问答平台

[![Tests](https://img.shields.io/badge/tests-102%20passing-brightgreen)](api/)
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

⚠️ **注意**: 本项目是独立开发的 RAG 平台，UI 设计灵感来自 Dify 但不依赖 Dify 代码库。

RAG（检索增强生成）私有化专业知识问答平台，支持高中低三种资源适配方案，实现数据层统一接入和灵活配置。

## ✨ 核心特性

### 🎯 三级资源适配
- **低资源**: SQLite + FTS5，适合个人/小团队，单机运行
- **中资源**: PostgreSQL + pgvector，适合中小企业，自托管可控
- **高资源**: Elasticsearch 集群，适合大型企业，高可用扩展

### 🔌 统一数据层
- 抽象 `BaseDataStore` 接口，屏蔽底层存储差异
- 支持 SQLite、PostgreSQL、Elasticsearch 多种后端
- 配置驱动切换，零代码修改

### 🔍 增强检索引擎
- 多路召回：向量 + 关键词 + 全文
- 融合策略：RRF（Reciprocal Rank Fusion）、加权融合
- 重排序：集成 BGE Reranker、Cohere Rerank

### 🎨 独立 UI 设计
- 现代化 Tailwind CSS UI
- 与 Dify 不同的视觉风格
- 响应式设计，支持暗色模式

## 🚀 快速开始

### 环境要求

- Python 3.7+ 或 Docker 20.10+
- 4GB+ 内存（推荐 8GB）

### 使用 Docker Compose（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-org/rag-platform.git
cd rag-platform

# 选择资源级别配置
cp docker-compose.medium.yml docker-compose.yml

# 启动服务
docker-compose up -d

# 访问界面
open http://localhost:3000
```

### 本地 Python 开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
python -m pytest api/ -v

# 启动 API（默认 SQLite 后端）
python -m api.app
```

### 配置资源级别

```bash
# 低资源（SQLite）
docker-compose -f docker-compose.low.yml up -d

# 中资源（PostgreSQL + pgvector）
docker-compose -f docker-compose.medium.yml up -d

# 高资源（Elasticsearch 集群）
docker-compose -f docker-compose.high.yml up -d
```

## 📖 文档

### 用户文档
- [部署指南](docs/deployment-guide.md) - 生产环境部署手册
- [开发指南](docs/development-guide.md) - 开发环境搭建与贡献指南
- [API 文档](docs/api-documentation.md) - 完整 API 参考

### 产品文档
- [产品需求文档 (PRD)](deliverables/prd/full-prd.md)
- [用户手册](docs/user-manual.md)

### 技术文档
- [技术架构设计](deliverables/architecture/technical-architecture.md)
- [数据库设计](deliverables/architecture/database-design.md)
- [API 规范](deliverables/architecture/api-spec.md)

### 项目文档
- [实施计划](deliverables/execution/implementation-plan.md)
- [Agent 协作指南](deliverables/agents/agent-system-overview.md)

## 🏗️ 架构概览

```
                    React Frontend
              + 资源适配配置 + 监控面板
                          |
              Flask/FastAPI API Layer
    +-------------+ +-------------+ +-----------------+
    |  Resource   | |   Unified   | |    Enhanced     |
    |  Config     | |   Data      | |    Retrieval    |
    |  Service    | |   Layer     | |    Engine       |
    +-------------+ +-------------+ +-----------------+
                          |
              Backend Adapter Layer
    +----------+ +----------+ +----------+
    |  SQLite  | |PGVector  | |    ES    |
    |  + FTS5  | |+tsvector | |  Cluster |
    +----------+ +----------+ +----------+
```

## 🛠️ 技术栈

### 后端
- **框架**: Python, Flask/FastAPI
- **数据库**: PostgreSQL + pgvector, SQLite + FTS5, Elasticsearch
- **向量检索**: pgvector, Elasticsearch dense_vector
- **全文检索**: PostgreSQL tsvector, SQLite FTS5, Elasticsearch BM25

### 前端
- **框架**: React 18, TypeScript, Next.js (App Router)
- **UI 组件**: shadcn/ui, Tailwind CSS
- **图表**: ECharts, Recharts

### 部署
- **容器化**: Docker, Docker Compose
- **CI/CD**: GitHub Actions
- **监控**: Prometheus, Grafana

## 📊 性能指标

| 资源级别 | 数据规模 | 查询延迟 | 并发 QPS | 内存占用 |
|----------|----------|----------|----------|----------|
| 低 | < 1万文档 | < 500ms | 10 | < 512MB |
| 中 | 1万-100万 | < 200ms | 1000 | < 4GB |
| 高 | > 100万 | < 100ms | 10000 | 按需扩展 |

## 🧪 测试

```bash
# 运行全部测试
python -m pytest api/ -v

# 运行集成测试
python -m pytest api/core/rag/datasource/unified/tests/test_three_tier_flow.py -v

# 性能基准测试
python scripts/benchmark.py --backend sqlite --docs 1000 --queries 100
```

当前测试状态: **102 tests passing** (81 单元测试 + 21 集成测试)

## 🤝 贡献指南

### 开发流程

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交变更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- Python: Black, Flake8, MyPy
- TypeScript: ESLint, Prettier
- 提交信息: Conventional Commits

### 测试要求

- 单元测试覆盖率 > 80%
- 集成测试覆盖三种资源级别
- 性能测试基准达标

## 📄 许可证

本项目基于 [Apache License 2.0](LICENSE) 开源。

## 🙏 致谢

- [Dify](https://github.com/langgenius/dify) - LLM 应用开发平台
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL 向量扩展
- [Elasticsearch](https://www.elastic.co/) - 分布式搜索引擎

## 📞 联系我们

- 项目仓库: [GitHub](https://github.com/your-org/rag-platform)
- 问题反馈: [GitHub Issues](https://github.com/your-org/rag-platform/issues)
- 文档站点: [Documentation](https://docs.rag-platform.dev)

---

**[回到顶部](#rag-私有化专业知识问答平台)**

Made with care by the RAG Platform Team
