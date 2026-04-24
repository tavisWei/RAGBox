# RAG 私有化专业知识问答平台 - Agent 协作指南

## 项目概述

基于 Dify 二次开发的 RAG 私有化专业知识问答平台，支持高中低三种资源适配方案。

## 核心特性

- **资源自适应**：低/中/高三种资源级别，自动选择最优检索后端
- **数据层统一**：抽象 `BaseDataStore` 接口，支持 SQLite、PostgreSQL、Elasticsearch
- **混合检索**：向量 + 关键词 + 全文，多路召回 + 融合
- **Dify 集成**：保持兼容，通过扩展点增强能力

## 技术栈

- **后端**: Python, Flask/FastAPI, PostgreSQL, Elasticsearch, SQLite
- **前端**: React, TypeScript, Next.js, shadcn/ui, Tailwind CSS
- **部署**: Docker, Docker Compose

## 项目结构

```
rag-reseacher/
├── deliverables/
│   ├── prd/                    # 产品需求文档
│   ├── architecture/           # 技术架构文档
│   ├── design/                 # 设计规范
│   ├── execution/              # 实施计划
│   └── agents/                 # Agent 协作文档
├── docs/                       # 项目文档
└── README.md
```

## 快速开始

1. 阅读 `deliverables/prd/full-prd.md` 了解产品需求
2. 阅读 `deliverables/architecture/technical-architecture.md` 了解技术架构
3. 查看 `deliverables/execution/implementation-plan.md` 了解实施计划

## Agent 角色

| 角色 | 职责 | 文档 |
|------|------|------|
| Project Manager | 项目协调、进度跟踪 | `deliverables/agents/agent-system-overview.md` |
| Backend | 后端开发、API 实现 | `deliverables/architecture/technical-architecture.md` |
| Frontend | 前端开发、UI 实现 | `deliverables/architecture/technical-architecture.md` |
| DevOps | 部署运维、CI/CD | `deliverables/architecture/technical-architecture.md` |
| QA | 测试验证、质量保障 | `deliverables/execution/implementation-plan.md` |

## 协作规范

1. **每日更新**: 各 Agent 每日提交进度更新
2. **代码审查**: 所有代码变更必须经过审查
3. **文档同步**: 技术变更必须同步更新文档
4. **问题升级**: 阻塞项 2 小时内必须响应

## 关键文档索引

- [产品需求文档](deliverables/prd/full-prd.md)
- [技术架构设计](deliverables/architecture/technical-architecture.md)
- [数据库设计](deliverables/architecture/database-design.md)
- [API 规范](deliverables/architecture/api-spec.md)
- [实施计划](deliverables/execution/implementation-plan.md)
- [Agent 协作指南](deliverables/agents/agent-system-overview.md)

## 联系方式

- 项目仓库: [GitHub Repository]
- 问题跟踪: [GitHub Issues]
- 文档站点: [Documentation Site]
