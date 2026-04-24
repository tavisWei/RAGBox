# RAGBox

> 轻量级、私有化、低运行成本的 RAG 知识问答系统。  
> 目标是做一个保留 Dify 核心体验、但更轻、更适合本地到企业自托管场景的 RAG 产品。

## 项目简介

RAGBox 是一个面向私有化知识库问答场景的项目，当前仓库已经包含：

- Python + FastAPI 后端
- Vue 3 前端
- 文档解析、分块、检索、问答完整链路
- 支持按资源级别切换不同后端能力
- 本地开发可直接通过脚本安装和启动

如果你想要的是：

- 比 Dify 更轻
- 更容易本地跑起来
- 更容易按自己业务做二开
- 更适合私有数据场景

那 RAGBox 就是这个方向。

---

## 核心特点

- **更轻**：优先解决 RAG 私有知识问答，不做过重的平台堆叠
- **更省资源**：支持低 / 中 / 高三档资源适配思路
- **更容易上手**：本地通过脚本直接安装、启动
- **更容易二开**：代码结构清晰，前后端分离
- **更适合私有化**：本地运行数据默认放在 `api/data/`

---

## 和 Dify 的区别

| 对比项 | Dify | RAGBox |
|---|---|---|
| 产品定位 | 通用 LLM 应用平台 | 聚焦 RAG 私有知识问答 |
| 运行成本 | 相对更重 | 相对更轻 |
| 本地启动 | 依赖更多服务 | 当前仓库脚本可直接启动 |
| 二次开发 | 平台能力更全，理解成本更高 | 聚焦核心链路，更适合按需改造 |
| 适合场景 | 通用 AI 平台化 | 本地 / 私有化 / 企业知识库 |

一句话：**Dify 更全，RAGBox 更轻、更聚焦。**

---

## 和同类项目相比的优势

RAGBox 当前最有价值的点，不是“功能最多”，而是：

1. **专注 RAG 私有问答本身**，不是把一切都做成大而全平台
2. **保留扩展空间**，但当前仓库仍然以可落地、可跑通为优先
3. **本地开发体验简单**，安装和启动成本低
4. **资源分层思路清晰**，适合从个人环境逐步过渡到企业环境

---

## 一键安装

环境要求：

- Python 3.10+
- Node.js 20+
- npm 10+

安装：

```bash
git clone https://github.com/tavisWei/RAGBox.git
cd RAGBox
./install.sh
```

这个脚本会完成：

- 创建 Python 虚拟环境
- 安装后端依赖
- 安装前端依赖
- 初始化本地运行目录

---

## 一键启动

```bash
./start.sh
```

启动后默认地址：

- 前端：http://localhost:3003
- 后端：http://localhost:8000
- 健康检查：http://localhost:8000/api/v1/health

默认管理员账号：

- 邮箱：`admin@example.com`
- 密码：`admin`

---

## 重启 / 更新 / 清空本地数据

### 重启

直接重新执行：

```bash
./start.sh
```

### 更新

拉取最新代码后，重新执行安装脚本即可：

```bash
git pull
./install.sh
./start.sh
```

### 清空本地运行数据

```bash
python scripts/reset_local_data.py
```

说明：

- 本地运行数据默认在 `api/data/`
- 这些数据属于运行时数据，不建议直接提交到仓库

---

## 当前技术架构

### 架构总览

```text
前端（Vue 3）
    ↓
API 层（FastAPI）
    ↓
RAG 服务层
    ├─ 文档解析
    ├─ 文本分块
    ├─ Embedding
    ├─ 多路检索
    ├─ 融合 / 重排
    └─ LLM 问答
    ↓
统一数据层
    ├─ SQLite + FTS5
    ├─ PostgreSQL + pgvector
    └─ Elasticsearch
```

### 技术选型

**后端：**

- FastAPI
- SQLAlchemy
- SQLite / PostgreSQL / Elasticsearch
- OpenAI / Ollama / HuggingFace 相关接入

**前端：**

- Vue 3
- TypeScript
- Vite
- Element Plus

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
└── start.sh            # 启动脚本
```

---

## 适合谁用

RAGBox 适合这些场景：

- 本地私有知识库问答
- 团队内部文档助手
- 企业私有化知识系统
- 想做一个比 Dify 更轻的 RAG 系统
- 想基于现有代码快速做行业化改造

---

## 文档入口

- [开发指南](docs/development-guide.md)
- [部署指南](docs/deployment-guide.md)
- [API 文档](docs/api-documentation.md)
- [技术架构文档](deliverables/architecture/technical-architecture.md)

---

## License

Apache License 2.0

---

如果这个项目对你有帮助，欢迎 Star。
