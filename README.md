# RAGBox

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/vue-3.5-4FC08D.svg" alt="Vue 3.5">
  <img src="https://img.shields.io/badge/fastapi-0.104-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/RAG-Production%20Ready-success.svg" alt="RAG Ready">
</p>

<p align="center">
  <b>轻量级、私有化、三级资源适配的 RAG 知识问答系统</b><br>
  <i>Lightweight, Self-hosted, Three-tier Resource-Adaptive RAG Knowledge Q&A Platform</i>
</p>

<p align="center">
  <a href="#quick-start">快速开始</a> •
  <a href="#features">核心特性</a> •
  <a href="#comparison">项目对比</a> •
  <a href="#architecture">架构设计</a> •
  <a href="#deployment">部署指南</a> •
  <a href="#api">API文档</a>
</p>

---

## 📖 简介 | Introduction

**RAGBox** 是一个专为私有化部署设计的 RAG（检索增强生成）知识问答平台。与 Dify 等重型方案不同，RAGBox 采用**三级资源适配架构**，让你能够从个人笔记本到企业级集群无缝部署，无需修改代码，仅通过配置即可切换底层存储和检索引擎。

**RAGBox** is a RAG (Retrieval-Augmented Generation) knowledge Q&A platform designed for privatized deployment. Unlike heavyweight solutions like Dify, RAGBox adopts a **three-tier resource-adaptive architecture**, allowing seamless deployment from personal laptops to enterprise clusters without code changes.

### 为什么选 RAGBox？| Why RAGBox?

| 痛点 | 传统方案 | RAGBox 方案 |
|------|---------|------------|
| 资源占用高 | Dify 需要 4GB+ 内存 | 最低 512MB 内存即可运行 |
| 部署复杂 | 8+ 个容器服务 | 单进程或简单双进程架构 |
| 学习成本高 | 需要理解微服务架构 | 配置驱动，零代码切换 |
| 数据隐私 | 依赖第三方云服务 | 完全私有化，数据不出境 |
| 扩展困难 | 垂直扩展成本高 | 三级架构平滑升级 |

---

## ✨ 核心特性 | Core Features {#features}

### 🎯 三级资源适配 | Three-Tier Resource Adaptation

```
┌─────────────────────────────────────────────────────────────────┐
│  High Resource (Elasticsearch Cluster + OpenAI Embedding)       │
│  >1M documents, <100ms latency, enterprise HA                   │
│  For: Large enterprises, massive knowledge bases                │
├─────────────────────────────────────────────────────────────────┤
│  Medium Resource (PostgreSQL + pgvector + HNSW)                 │
│  10K-1M documents, <200ms latency, production ready             │
│  For: SMBs, standard production deployment                      │
├─────────────────────────────────────────────────────────────────┤
│  Low Resource (SQLite + FTS5 + Local Embedding)                 │
│  <10K documents, <500ms latency, zero-config single file        │
│  For: Individuals, small teams, edge devices, prototypes        │
└─────────────────────────────────────────────────────────────────┘
```

- **配置驱动切换**: Environment variable `DATA_STORE_TYPE=sqlite|pgvector|elasticsearch`
- **零代码迁移**: Same API, different performance characteristics
- **渐进式升级**: Start with SQLite, migrate to PostgreSQL or ES as you grow

### 🔍 增强检索引擎 | Enhanced Retrieval Engine

- **Multi-Way Retrieval**: Vector + Full-text + Keyword search in parallel
- **Smart Fusion**: RRF (Reciprocal Rank Fusion) and weighted fusion strategies
- **Reranking**: Cross-Encoder and LLM Listwise reranking
- **Query Expansion**: Multi-Query, HyDE strategies

### 📚 统一数据层 | Unified Data Layer

```python
# Same interface regardless of backend: SQLite, PostgreSQL, or Elasticsearch
from api.core.rag.datasource.unified import DataStoreFactory

store = DataStoreFactory.create("sqlite")  # or "pgvector", "elasticsearch"
store.create_collection("my_kb", dimension=1536)
store.add_documents("my_kb", documents, embeddings)
results = store.search("my_kb", query="What is RAG?", search_method="hybrid")
```

### 🤖 多模型支持 | Multi-Model Support

**当前已接入 / Implemented now**

**Embedding:**
- OpenAI
- Ollama
- HuggingFace

**LLM:**
- OpenAI-compatible chat
- Ollama local chat
- Demo provider for local validation

**扩展性 / Extensibility**
- 仓库内已经提供 provider 抽象层，便于后续扩展更多模型供应商
- A provider abstraction layer is already in place for future model integrations

### 📄 文档处理 | Document Processing

Supported formats: PDF, Word (DOCX), PowerPoint (PPTX), Excel (XLSX), HTML, Markdown, Plain Text

Chunking strategies:
- **Fixed Size**: Even chunking by character count
- **Semantic**: Smart splitting by sentence/paragraph boundaries
- **Recursive**: Hierarchical splitting by headings

### 🎨 现代化前端 | Modern Frontend

- **Vue 3 + TypeScript**: Composition API, type-safe
- **Element Plus**: Enterprise UI component library
- **Workflow Editor**: Visual workflow orchestration with @vue-flow
- **Responsive Design**: Desktop, tablet, mobile adaptive

---

## 🚀 快速开始 | Quick Start {#quick-start}

### 环境要求 | Requirements

- Python 3.10+
- Node.js 20+
- npm 10+

### 安装 | Installation

```bash
# Clone repository
git clone https://github.com/tavisWei/RAGBox.git
cd RAGBox

# One-click installation (creates virtualenv, installs dependencies)
./install.sh
```

The install script will:
- Create Python virtual environment (`.venv`)
- Install backend dependencies (`requirements.txt`)
- Install frontend dependencies (`web-vue/`)
- Create local data directory (`api/data/`)

### 启动 | Start

```bash
# Start backend + frontend (development mode)
./start.sh
```

Services will be available at:
- 🌐 Frontend: http://localhost:3003
- 🔌 API: http://localhost:8000
- 💓 Health Check: http://localhost:8000/api/v1/health

Default admin account:
- Email: `admin@example.com`
- Password: `admin`

### 配置模型提供商 | Configure Model Provider

First-time setup requires configuring model providers in the UI:

1. Login and go to "System Settings" → "Model Providers"
2. Add OpenAI, Ollama, or other compatible APIs
3. Configure Embedding model and LLM model
4. Create a knowledge base and start uploading documents

---

## 🏗️ 架构设计 | Architecture {#architecture}

### 逻辑架构图 | Logical Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Knowledge   │  │  Chat       │  │  Workflow Editor        │  │
│  │ Base Mgmt   │  │  Interface  │  │  (Vue Flow)             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                           │
│                    FastAPI + Pydantic + JWT                      │
│         /api/v1/knowledge-bases  /api/v1/retrieve               │
│         /api/v1/chat            /api/v1/apps                    │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Resource     │  │ Unified      │  │ Enhanced Retrieval   │  │
│  │ Config Svc   │  │ Data Layer   │  │ Engine               │  │
│  │ (3-tier)     │  │ (Unified API)│  │ (Multi-way + Fusion) │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Data Access Layer                           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  SQLite  │  │  PostgreSQL  │  │   Elasticsearch          │  │
│  │  + FTS5  │  │  + pgvector  │  │   Cluster                │  │
│  │  (Low)   │  │  (Medium)    │  │   (High)                 │  │
│  └──────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 技术架构 | Technical Architecture

**Backend Stack:**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Framework | FastAPI 0.104 | High-performance async API |
| Data Validation | Pydantic 2.5 | Request/response models |
| ORM | SQLAlchemy 2.0 | Database abstraction |
| Vector Search | pgvector / ES dense_vector | Semantic search |
| Full-text Search | SQLite FTS5 / PostgreSQL tsvector / ES BM25 | Text matching |
| Document Parsing | pypdf, python-docx, BeautifulSoup | Multi-format support |
| Chinese NLP | jieba, pkuseg | Chinese tokenization |

**Frontend Stack:**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Vue 3.5 | Reactive UI |
| Language | TypeScript | Type safety |
| Build Tool | Vite 8 | Fast development |
| UI Library | Element Plus 2.13 | Component library |
| State Management | Pinia 3 | State management |
| Workflow | @vue-flow/core | Visual orchestration |

---

## 📊 项目对比 | Comparison {#comparison}

### vs Dify

| Dimension | Dify | RAGBox | Advantage |
|-----------|------|--------|-----------|
| **Resource Usage** | 4GB+ RAM, 8+ services | 512MB-4GB RAM, 1-2 processes | RAGBox saves 80%+ resources |
| **Deployment Complexity** | Docker Compose 8 containers | Single script startup | RAGBox one-click start |
| **Architecture** | Microservices | Modular monolith | RAGBox simpler |
| **Learning Curve** | Steep | Gentle | RAGBox easier to learn |
| **Feature Coverage** | Full LLM app platform | Focused on RAG core | RAGBox more focused |
| **Customization** | Need to understand multi-service | Single codebase | RAGBox easier to customize |
| **Use Case** | Large enterprises, complex workflows | SMBs, rapid deployment | Different focuses |

**Recommendation:**
- Need full LLM app platform, complex Agent workflows → **Dify**
- Focus on knowledge base Q&A, lightweight, resource-constrained → **RAGBox**

### vs Alternatives

| Project | Type | Min RAM | Architecture | Key Feature | Best For |
|---------|------|---------|-------------|-------------|----------|
| **RAGBox** | Platform | 512MB | 3-tier adaptive | Config-driven, resource-adaptive | All scenarios |
| Dify | Platform | 4GB | Microservices | Most complete, rich ecosystem | Large enterprises |
| FastGPT | Platform | 4GB | Monolithic | Multi-vector mapping, Flow | Medium scale |
| AnythingLLM | App | 2GB | Desktop+Server | Minimalist, MIT license | Individuals/small teams |
| OpenWebUI | Interface | 1GB | Stateless | Largest community, extensible | Multi-user scenarios |
| LangChain | Framework | 200MB | Library | Flexible, rich integrations | Custom development |
| LlamaIndex | Framework | 150MB | Library | RAG-specialized, retrieval-optimized | Document-intensive |

**RAGBox Unique Advantages:**
1. **Only 3-tier resource adaptation**: SQLite to ES cluster, one codebase covers all
2. **Truly config-driven**: Zero-code backend switching
3. **Unified data layer abstraction**: Backend-agnostic retrieval interface
4. **Production-grade retrieval engine**: RRF fusion, reranking, query expansion

---

## 📦 部署指南 | Deployment Guide {#deployment}

### Low Resource (SQLite)

Best for: Individual developers, edge devices, rapid prototyping

```bash
# Environment variables
export DATA_STORE_TYPE=sqlite
export SQLITE_DB_PATH=/data/ragbox.sqlite
export RESOURCE_LEVEL=low

# Start
./start.sh
```

**Requirements:**
- CPU: 1 core
- RAM: 512MB
- Storage: 10GB SSD

### Medium Resource (PostgreSQL)

Best for: SMB production environments

```bash
# Environment variables
export DATA_STORE_TYPE=pgvector
export PGVECTOR_HOST=localhost
export PGVECTOR_PORT=5432
export PGVECTOR_DATABASE=ragbox
export PGVECTOR_USER=ragbox
export PGVECTOR_PASSWORD=your-password
export RESOURCE_LEVEL=medium

# Start
./start.sh
```

**Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 100GB SSD

**PostgreSQL Setup:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### High Resource (Elasticsearch)

Best for: Large enterprises, massive documents, high concurrency

```bash
# Environment variables
export DATA_STORE_TYPE=elasticsearch
export ELASTICSEARCH_HOSTS=http://es-node1:9200,http://es-node2:9200
export ELASTICSEARCH_USERNAME=elastic
export ELASTICSEARCH_PASSWORD=your-password
export RESOURCE_LEVEL=high

# Start
./start.sh
```

**Requirements:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: Distributed cluster, scale as needed

### 运维方法 | Operations

#### Daily Operations

1. **Health check**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
2. **Process management**
   - Local development: use `./start.sh`
   - Production: manage the backend/frontend processes with your own supervisor or platform tooling
3. **Runtime data management**
   - Local runtime data lives in `api/data/`
   - Keep `api/data/` mounted outside the repo in real deployments
4. **Backup strategy**
   - SQLite: back up the database file under `api/data/`
   - PostgreSQL: use `pg_dump`
   - Elasticsearch: use cluster snapshots

#### Reset Local Runtime Data

```bash
python scripts/reset_local_data.py
```

#### Production Recommendations

1. **Use external databases**: PostgreSQL or Elasticsearch for production instead of SQLite
2. **Use a reverse proxy**: Nginx / Traefik for HTTPS and routing
3. **Separate runtime data from code**: do not persist business data inside the git working tree
4. **Store secrets outside the repo**: environment variables or secret manager only

### 更新方法 | Upgrade Guide

```bash
git pull
./install.sh
./start.sh
```

Recommended upgrade workflow:

1. Back up runtime data first
2. Pull latest code
3. Reinstall dependencies with `./install.sh`
4. Restart with `./start.sh`
5. Verify `/api/v1/health`

---

## 🔧 配置参考 | Configuration Reference

### Environment Variables

| Variable | Description | Default | Level |
|----------|-------------|---------|-------|
| `DATA_STORE_TYPE` | Storage backend type | `sqlite` | All |
| `RESOURCE_LEVEL` | Resource level | `medium` | All |
| `SQLITE_DB_PATH` | SQLite database path | `api/data/rag.sqlite` | Low |
| `PGVECTOR_HOST` | PostgreSQL host | `localhost` | Medium |
| `PGVECTOR_PORT` | PostgreSQL port | `5432` | Medium |
| `PGVECTOR_DATABASE` | PostgreSQL database | `ragbox` | Medium |
| `PGVECTOR_USER` | PostgreSQL username | `ragbox` | Medium |
| `PGVECTOR_PASSWORD` | PostgreSQL password | - | Medium |
| `ELASTICSEARCH_HOSTS` | ES node addresses | `http://localhost:9200` | High |
| `ELASTICSEARCH_USERNAME` | ES username | - | High |
| `ELASTICSEARCH_PASSWORD` | ES password | - | High |
| `OPENAI_API_KEY` | OpenAI API key | - | All |
| `OLLAMA_BASE_URL` | Ollama service URL | `http://localhost:11434` | All |
| `API_PORT` | Backend port | `8000` | All |
| `WEB_PORT` | Frontend port | `3003` | All |

### Resource Level Details

| Config | Low | Medium | High |
|--------|-----|--------|------|
| **Storage Backend** | SQLite | PostgreSQL + pgvector | Elasticsearch |
| **Max Documents** | 10,000 | 1,000,000 | Unlimited |
| **Vector Search** | Optional (numpy) | Yes (HNSW) | Yes (kNN) |
| **Full-text Search** | FTS5 | tsvector | BM25 |
| **Fusion Strategy** | RRF | RRF | RRF |
| **Reranking** | None | Cross-Encoder | LLM Listwise |
| **Query Expansion** | None | Multi-Query | HyDE |
| **Embedding Model** | Ollama local | OpenAI small | OpenAI large |
| **Chunk Size** | 500 | 500 | 1000 |
| **Expected Latency** | <500ms | <200ms | <100ms |

---

## 📚 API 文档 | API Documentation {#api}

### Core Endpoints

#### Health Check
```bash
GET /api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

#### Create Knowledge Base
```bash
POST /api/v1/knowledge-bases
Content-Type: application/json

{
  "name": "Product Docs",
  "description": "Company product knowledge base",
  "resource_level": "medium"
}
```

#### Upload Document
```bash
POST /api/v1/knowledge-bases/{kb_id}/documents
Content-Type: multipart/form-data

file: @document.pdf
```

#### Retrieve
```bash
POST /api/v1/retrieve
Content-Type: application/json

{
  "knowledge_base_id": "kb-xxx",
  "query": "What is RAG?",
  "top_k": 10,
  "search_method": "hybrid"
}
```

#### Chat
```bash
POST /api/v1/chat
Content-Type: application/json

{
  "knowledge_base_id": "kb-xxx",
  "message": "Explain how RAG works",
  "conversation_id": "conv-xxx",
  "stream": false
}
```

#### Streaming Chat
```bash
POST /api/v1/chat
Content-Type: application/json

{
  "knowledge_base_id": "kb-xxx",
  "message": "Explain how RAG works",
  "stream": true
}
```

Response: SSE (Server-Sent Events)

Full API documentation: [API Documentation](docs/api-documentation.md)

---

## 🛠️ 开发指南 | Development Guide

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/tavisWei/RAGBox.git
cd RAGBox

# 2. Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd web-vue
npm install
cd ..

# 5. Start backend (Terminal 1)
python -m uvicorn api.main:app --reload --port 8000

# 6. Start frontend (Terminal 2)
cd web-vue
npm run dev -- --port 3003
```

### Running Tests

```bash
# Run all tests
python -m pytest api/ -v

# Run specific tests
python -m pytest api/tests/test_api.py -v

# Run coverage tests
python -m pytest api/ --cov=api --cov-report=html

# Performance benchmark
python scripts/benchmark.py --backend sqlite --docs 1000 --queries 100
```

### Code Style

**Python:**
- Formatter: Black
- Linter: Flake8, MyPy
- Import sorting: isort

```bash
black api/
flake8 api/
mypy api/
```

**TypeScript/Vue:**
- Formatter: Prettier
- Linter: ESLint, oxlint

```bash
cd web-vue
npm run lint
npm run format
```

### Commit Convention

Using [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix bug
docs: documentation update
style: code formatting (no functional change)
refactor: refactoring
test: test related
chore: build/tool related
```

---

## 📈 资源适配建议 | Resource Planning

> 以下是面向部署规划的建议区间，用于帮助选型；并非仓库内自动跑出的基准测试报告。

| Resource Level | Backend | Suggested Scale | Suggested Memory | Typical Scenario |
|---------------|---------|-----------------|------------------|------------------|
| Low | SQLite + FTS5 | < 10K docs | 512MB+ | 개인/个人、本地验证、小团队 |
| Medium | PostgreSQL + pgvector | 10K - 1M docs | 4GB+ | SMB、自托管生产 |
| High | Elasticsearch | 1M+ docs | 8GB+ / cluster | Enterprise, high availability |

---

## 🗺️ 路线图 | Roadmap

### Completed
- [x] Three-tier resource adaptation architecture
- [x] Unified data layer abstraction
- [x] Multi-way retrieval + RRF fusion
- [x] Cross-Encoder reranking
- [x] Multi-format document parsing
- [x] Vue 3 frontend interface
- [x] Visual workflow orchestration
- [x] OpenAI / Ollama integration

### In Progress
- [ ] Knowledge graph enhanced retrieval
- [ ] Multi-modal document support (images, audio)
- [ ] Agent workflow nodes
- [ ] Real-time collaborative editing

### Planned
- [ ] Federated retrieval (cross-knowledge-base search)
- [ ] Automatic evaluation and optimization
- [ ] Enterprise SSO integration
- [ ] Mobile app

---

## 🤝 贡献指南 | Contributing

We welcome all forms of contributions!

### How to Contribute

1. **Fork** this repository
2. Create feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m 'feat: add some AmazingFeature'`
4. Push branch: `git push origin feature/AmazingFeature`
5. Create **Pull Request**

### Contribution Types

- 🐛 **Bug Fixes**: Submit Issue describing the problem, or fix directly
- ✨ **New Features**: Open Issue to discuss design first
- 📚 **Documentation**: Fix errors, add examples
- 🧪 **Test Coverage**: Add unit tests, integration tests
- 🎨 **UI/UX**: Frontend interface improvements

See [Development Guide](docs/development-guide.md) for details.

---

## 📄 许可证 | License

This project is licensed under [Apache License 2.0](LICENSE).

```
Copyright 2026 RAGBox Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## 🙏 致谢 | Acknowledgments

- [Dify](https://github.com/langgenius/dify) - LLM app development platform, UI design inspiration
- [FastAPI](https://fastapi.tiangolo.com/) - High-performance Python web framework
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL vector extension
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [Element Plus](https://element-plus.org/) - Vue 3 component library

---

## 📞 联系我们 | Contact

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/tavisWei/RAGBox/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/tavisWei/RAGBox/discussions)

---

<p align="center">
  <b>⭐ Star us if you find this project helpful!</b><br>
</p>

<p align="center">
  Made with ❤️ by the RAGBox Team
</p>
