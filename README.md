# RAGBox

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/vue-3.5-4FC08D.svg" alt="Vue 3.5">
  <img src="https://img.shields.io/badge/fastapi-0.104-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License">
</p>

<p align="center">
  <b>轻量级、私有化、三级资源适配的 RAG 知识问答系统</b><br>
  面向本地开发到企业自托管场景，专注把 RAG 私有知识问答做得更轻、更容易部署、更容易二开。
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> •
  <a href="#核心特性">核心特性</a> •
  <a href="#项目对比">项目对比</a> •
  <a href="#架构设计">架构设计</a> •
  <a href="#部署与运维">部署与运维</a> •
  <a href="#文档入口">文档入口</a>
</p>

---

## 简介

**RAGBox** 是一个面向私有化部署的 RAG（检索增强生成）知识问答系统。

它的目标不是做一个大而全的通用 AI 平台，而是聚焦在 **RAG 私有知识问答** 这条链路上，把“本地可跑、资源更轻、易于改造、适合企业私有化”这几件事做好。

与 Dify 等偏重型的平台方案相比，RAGBox 更强调：

- 更低的运行成本
- 更直接的本地启动体验
- 更容易理解和二次开发
- 更适合从个人开发到企业内部系统逐步演进

---

## 为什么选 RAGBox？

| 痛点 | 常见重型方案 | RAGBox 方案 |
|---|---|---|
| 资源占用高 | 需要更多服务和更高内存 | 本地可用更轻量方式启动 |
| 部署复杂 | 依赖较多基础设施 | 当前仓库以脚本化安装/启动为主 |
| 学习成本高 | 平台能力多，理解范围大 | 聚焦知识库问答核心链路 |
| 二开门槛高 | 系统面较大 | 前后端分离，便于按需改造 |
| 私有数据顾虑 | 需要更多外部依赖协调 | 更适合本地和私有化场景 |

---

## 核心特性

### 三级资源适配

RAGBox 的设计思路是让同一套项目能够覆盖不同资源条件下的使用场景：

```text
高资源：Elasticsearch 集群 + 更强检索能力
中资源：PostgreSQL + pgvector
低资源：SQLite + FTS5 + 本地轻量运行
```

这意味着你可以：

- 从本地开发开始
- 先用低成本方案验证
- 再按业务规模逐步升级后端能力

### 增强检索引擎

当前项目设计和实现中，重点围绕 RAG 检索效果做增强：

- 多路召回
- 检索结果融合
- 重排序
- 查询扩展

目标是让它不仅能“查到”，还尽量“查得准、答得稳”。

### 统一数据层

项目对底层数据存储做了统一抽象，目标是让不同后端具备一致的接入方式，降低迁移和切换成本。

当前主要面向：

- SQLite
- PostgreSQL + pgvector
- Elasticsearch

### 多模型支持

当前仓库已经覆盖或预留了这些模型接入方向：

**Embedding：**

- OpenAI
- Ollama
- HuggingFace

**LLM：**

- OpenAI 兼容接口
- Ollama 本地模型
- Demo provider（便于本地验证）

### 文档处理能力

面向知识库场景，项目支持常见文档处理链路：

- 文档导入
- 文本抽取
- 文本分块
- 向量化
- 检索问答

支持的文档类型包括：

- PDF
- Word（DOCX）
- PowerPoint（PPTX）
- Excel（XLSX）
- HTML
- Markdown
- 纯文本

### 现代化前端

前端基于 Vue 3 技术栈，重点是提供面向知识库问答与配置管理的现代化界面。

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 20+
- npm 10+

### 一键安装

```bash
git clone https://github.com/tavisWei/RAGBox.git
cd RAGBox
./install.sh
```

`install.sh` 会自动完成：

- 创建 Python 虚拟环境
- 安装后端依赖
- 安装前端依赖
- 初始化本地运行目录 `api/data/`

### 一键启动

```bash
./start.sh
```

启动成功后默认地址：

- 前端：http://localhost:3003
- 后端：http://localhost:8000
- 健康检查：http://localhost:8000/api/v1/health

默认管理员账号：

- 邮箱：`admin@example.com`
- 密码：`admin`

### 首次使用建议

首次进入系统后，建议先完成：

1. 配置模型提供商
2. 配置 Embedding 模型
3. 配置问答模型
4. 创建知识库
5. 上传文档并测试问答效果

---

## 架构设计

### 逻辑架构图

```text
┌──────────────────────────────────────────────┐
│                  表现层                      │
│   知识库管理 / 对话界面 / 工作流相关界面      │
└──────────────────────────────────────────────┘
                     │
┌──────────────────────────────────────────────┐
│                  API 层                      │
│             FastAPI + 路由 + 鉴权            │
└──────────────────────────────────────────────┘
                     │
┌──────────────────────────────────────────────┐
│                业务逻辑层                    │
│   资源配置 / 统一数据层 / 检索引擎 / 问答服务   │
└──────────────────────────────────────────────┘
                     │
┌──────────────────────────────────────────────┐
│                数据访问层                    │
│   SQLite / PostgreSQL + pgvector / ES       │
└──────────────────────────────────────────────┘
```

### 技术架构

**后端技术栈：**

| 组件 | 技术选型 | 作用 |
|---|---|---|
| Web 框架 | FastAPI | API 服务 |
| 数据验证 | Pydantic | 请求/响应模型 |
| ORM/数据抽象 | SQLAlchemy | 数据访问 |
| 向量检索 | pgvector / ES dense_vector | 语义检索 |
| 全文检索 | SQLite FTS5 / PostgreSQL / ES | 文本检索 |
| 文档解析 | pypdf / python-docx / BeautifulSoup 等 | 文档处理 |

**前端技术栈：**

| 组件 | 技术选型 | 作用 |
|---|---|---|
| 框架 | Vue 3 | 前端 UI |
| 语言 | TypeScript | 类型安全 |
| 构建工具 | Vite | 开发与构建 |
| UI 库 | Element Plus | 组件系统 |

---

## 项目对比

### 对比 Dify

| 维度 | Dify | RAGBox |
|---|---|---|
| 产品定位 | 通用 LLM 应用平台 | 聚焦 RAG 私有知识问答 |
| 运行成本 | 更偏重 | 更偏轻 |
| 部署复杂度 | 更高 | 当前仓库更适合直接脚本启动 |
| 学习曲线 | 更长 | 更容易聚焦理解 |
| 二次开发 | 平台能力多，改造范围大 | 更适合按知识库问答场景定制 |

一句话：

**Dify 更全，RAGBox 更轻、更聚焦。**

### 与 Dify 的功能对比

> 说明：下表强调的是项目定位和当前仓库呈现出来的能力边界，不代表对 Dify 全部能力的完整覆盖，也不表示 RAGBox 要与 Dify 在所有方向上做一比一竞争。

| 功能项 | Dify | RAGBox |
|---|---|---|
| 知识库问答 | 支持 | 支持 |
| 私有化部署 | 支持 | 支持 |
| 本地快速启动 | 可实现，但整体更重 | 更强调脚本化直接启动 |
| 资源分层思路 | 相对不强调 | 强调低 / 中 / 高资源适配 |
| 多模型接入 | 强 | 已覆盖核心接入方向 |
| 工作流/编排 | 更完整 | 当前不是核心卖点 |
| 平台化能力 | 更强 | 当前聚焦知识问答主链路 |
| 二次开发聚焦度 | 平台能力丰富，改造面更大 | 更适合围绕知识问答直接改造 |
| 本地轻量体验 | 相对弱一些 | 更强调 |
| 企业内网知识助手 | 适合 | 适合，且更偏轻量化路线 |

### 对比同类项目

RAGBox 的优势不在于“功能面最广”，而在于：

- 更适合本地快速启动
- 更适合私有化知识问答场景
- 更适合低成本起步
- 更适合作为业务改造底座

如果你需要的是一个**聚焦 RAG 私有知识问答**、而不是一整套庞大 AI 平台，那么 RAGBox 会更合适。

---

## English Overview

**RAGBox** is a lightweight, self-hosted RAG knowledge Q&A system built for private deployment.

Instead of becoming an all-in-one AI platform, RAGBox focuses on one thing: making private knowledge retrieval and question answering easier to run, easier to understand, and easier to customize.

### Why RAGBox?

- Lightweight compared with heavyweight LLM platforms
- Easier local startup experience
- Better fit for private knowledge base scenarios
- Easier to customize for business-specific use cases
- Designed to evolve from local development to enterprise self-hosting

### Quick Start

```bash
git clone https://github.com/tavisWei/RAGBox.git
cd RAGBox
./install.sh
./start.sh
```

### Restart

```bash
./restart.sh
```

### Default URLs

- Frontend: http://localhost:3003
- Backend: http://localhost:8000
- Health Check: http://localhost:8000/api/v1/health

### Default Admin

- Email: `admin@example.com`
- Password: `admin`

---

## 部署与运维

### 低 / 中 / 高资源思路

| 资源级别 | 主要后端 | 适合场景 |
|---|---|---|
| 低 | SQLite + FTS5 | 本地开发、个人使用、小团队验证 |
| 中 | PostgreSQL + pgvector | 中小团队、自托管生产 |
| 高 | Elasticsearch | 企业级、大规模知识库 |

这部分代表的是项目设计与演进方向，不意味着你一开始就必须上复杂部署。

对当前仓库来说，**最直接的使用方式依然是脚本安装 + 脚本启动**。

### 更新方法

```bash
git pull
./install.sh
./restart.sh
```

推荐更新流程：

1. 先备份本地运行数据
2. 拉取最新代码
3. 重新执行安装脚本
4. 使用重启脚本拉起服务
5. 检查健康状态

### 重启方法

```bash
./restart.sh
```

`restart.sh` 会：

- 停掉占用当前前后端端口的进程
- 再执行 `start.sh` 重新拉起服务

默认端口：

- 后端：`8000`
- 前端：`3003`

如果你设置了 `API_PORT` / `WEB_PORT`，重启脚本也会沿用同样的端口配置。

### 清空本地运行数据

```bash
python scripts/reset_local_data.py
```

说明：

- 本地运行数据默认存放在 `api/data/`
- 这些文件属于运行时数据，不建议直接提交到仓库

### 日常运维建议

1. 使用健康检查确认服务状态：

```bash
curl http://localhost:8000/api/v1/health
```

2. 本地开发时直接使用脚本管理服务
3. 生产环境中将运行数据目录与代码目录分离
4. 将模型密钥、数据库密码等配置放到环境变量或外部密钥管理中

---

## 配置参考

### 常用环境变量

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `DATA_STORE_TYPE` | 存储后端类型 | `sqlite` |
| `RESOURCE_LEVEL` | 资源级别 | `medium` |
| `SQLITE_DB_PATH` | SQLite 数据库路径 | `api/data/rag.sqlite` |
| `PGVECTOR_HOST` | PostgreSQL 主机 | `localhost` |
| `PGVECTOR_PORT` | PostgreSQL 端口 | `5432` |
| `PGVECTOR_DATABASE` | PostgreSQL 数据库名 | `ragbox` |
| `PGVECTOR_USER` | PostgreSQL 用户名 | `ragbox` |
| `PGVECTOR_PASSWORD` | PostgreSQL 密码 | 空 |
| `ELASTICSEARCH_HOSTS` | Elasticsearch 地址 | `http://localhost:9200` |
| `OPENAI_API_KEY` | OpenAI API Key | 空 |
| `OLLAMA_BASE_URL` | Ollama 地址 | `http://localhost:11434` |
| `API_PORT` | 后端端口 | `8000` |
| `WEB_PORT` | 前端端口 | `3003` |

---

## 当前能力概览

结合当前仓库实现，可以把 RAGBox 理解为已经具备这些核心能力：

- 知识库基础管理
- 文档导入与处理
- 文本分块
- Embedding 接入
- 检索召回
- 融合与重排
- 基于知识库的问答
- 前后端联调运行

也就是说，它已经不是一个空壳概念项目，而是一个具备基本产品形态、适合继续工程化和业务化扩展的 RAG 私有知识问答项目。

---

## 开发说明

如果你需要进一步开发或二次改造，建议优先阅读：

- `api/`：后端代码
- `web-vue/`：前端代码
- `scripts/`：工具脚本
- `docs/`：开发和部署说明

本地开发最常用的命令仍然是：

```bash
./install.sh
./start.sh
./restart.sh
```

### 如何参与开发

推荐的参与方式：

1. Fork 本仓库
2. 创建新的开发分支
3. 完成修改并自测
4. 提交 commit
5. 发起 Pull Request

示例流程：

```bash
git checkout -b feature/your-feature-name
# 开发与修改
git add .
git commit -m "Add your feature"
git push origin feature/your-feature-name
```

### 提交建议

- 一个提交尽量只做一件事
- 文档修改、功能修改、脚本修改尽量分清楚
- 提交信息尽量清晰表达本次改动目的

推荐提交信息风格：

```text
Add xxx
Update xxx
Fix xxx
Refactor xxx
```

### 本地开发建议

- 后端改动后优先验证接口是否正常
- 前端改动后优先验证页面是否能正常启动
- 如果涉及启动流程，优先验证 `install.sh` / `start.sh` / `restart.sh`
- 不要把 `api/data/` 里的运行时数据当成源码提交

---

## 项目结构

```text
RAGBox/
├── api/                # 后端
├── web-vue/            # 前端
├── docs/               # 说明文档
├── deliverables/       # 设计与架构文档
├── scripts/            # 工具脚本
├── install.sh          # 安装脚本
├── start.sh            # 启动脚本
└── restart.sh          # 重启脚本
```

---

## 适合谁用

RAGBox 适合这些场景：

- 本地私有知识库问答
- 团队内部文档助手
- 企业私有化知识系统
- 想做一个比 Dify 更轻的 RAG 系统
- 想基于现有代码快速做行业化改造

如果你是下面这几类人，也会比较适合：

- 独立开发者
- AI 应用创业团队
- 企业内部工具团队
- 需要私有化知识问答能力的业务团队

---

## 文档入口

- [开发指南](docs/development-guide.md)
- [部署指南](docs/deployment-guide.md)
- [API 文档](docs/api-documentation.md)
- [技术架构文档](deliverables/architecture/technical-architecture.md)

---

## License

Apache License 2.0

### Apache License 2.0 说明

RAGBox 采用 Apache License 2.0 开源协议。

这意味着你通常可以：

- 使用本项目
- 修改本项目
- 在商业项目中使用本项目
- 分发你修改后的版本

你需要注意的是：

- 需要保留原始版权和许可证声明
- 如果你修改了代码，应该清晰标注变更
- 本项目按“现状”提供，不附带额外担保

如果你准备将 RAGBox 用于企业或商业场景，建议同时让法务或合规团队确认你们的内部使用要求。

> 注意：如果仓库根目录还没有正式的 `LICENSE` 文件，建议补充标准 Apache-2.0 文本文件，以保证仓库协议声明完整。

---

如果这个项目对你有帮助，欢迎 Star。也欢迎提交 Issue、PR 或者基于它继续做行业化产品扩展。
