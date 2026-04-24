# RAGBox

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/vue-3.5-4FC08D.svg" alt="Vue 3.5">
  <img src="https://img.shields.io/badge/fastapi-0.104-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License">
</p>

<p align="center">
  <b>轻量级、私有化、低运行成本的 RAG 知识问答系统</b><br>
  面向本地开发到企业自托管场景，专注把 RAG 私有知识问答做得更轻、更容易部署、更容易二开。
</p>

---

## 项目简介

RAGBox 是一个面向私有化知识库问答场景的项目。

它的目标不是做一个“大而全”的 AI 平台，而是把 **RAG 私有问答这条链路** 做得更轻、更稳、更适合真实项目落地。

当前仓库已经包含：

- Python + FastAPI 后端
- Vue 3 前端
- 文档解析、分块、检索、问答完整链路
- 多种后端存储适配思路
- 本地脚本化安装、启动、重启

如果你想要的是：

- 比 Dify 更轻
- 更容易本地跑起来
- 更容易按自己业务做二次开发
- 更适合私有数据和企业内网场景

那么 RAGBox 就是这个方向。

---

## 核心特点

### 1）更轻

RAGBox 优先解决的是 **RAG 私有知识问答**，而不是一次性把所有 AI 平台能力全部堆上来。

这样带来的好处是：

- 代码更聚焦
- 运行成本更低
- 学习成本更低
- 更适合本地起步和定制改造

### 2）更省资源

项目整体设计上支持低 / 中 / 高三档资源适配思路：

- **低资源**：本地开发、个人使用、小团队验证
- **中资源**：中小团队、自托管生产环境
- **高资源**：更大规模知识库和企业级场景

### 3）更容易上手

本地开发不强调复杂编排，而是优先提供简单直接的脚本方式：

- `install.sh`：安装
- `start.sh`：启动
- `restart.sh`：重启

### 4）更容易二开

项目当前结构比较清晰：

- `api/`：后端
- `web-vue/`：前端
- `scripts/`：辅助脚本
- `docs/`：说明文档

适合你继续做：

- 行业知识库
- 企业内部智能助手
- 私有化问答系统
- 业务化 RAG 产品

### 5）更适合私有化

本地运行数据默认在 `api/data/`，更适合：

- 本地调试
- 私有部署
- 数据和代码隔离管理

---

## 和 Dify 的区别

| 对比项 | Dify | RAGBox |
|---|---|---|
| 产品定位 | 通用 LLM 应用平台 | 聚焦 RAG 私有知识问答 |
| 运行成本 | 相对更重 | 相对更轻 |
| 本地启动 | 依赖更多服务 | 当前仓库脚本可直接启动 |
| 二次开发 | 平台能力更全，理解成本更高 | 聚焦核心链路，更适合按需改造 |
| 适合场景 | 通用 AI 平台化 | 本地 / 私有化 / 企业知识库 |

一句话总结：

**Dify 更全，RAGBox 更轻、更聚焦。**

---

## 和同类项目相比的优势

RAGBox 当前最有价值的点，不是“功能最多”，而是：

1. **专注 RAG 私有问答本身**，不是做成大而全平台
2. **保留扩展空间**，但以可落地、可跑通为优先
3. **本地开发体验简单**，安装和启动成本低
4. **资源分层思路清晰**，适合从个人环境逐步过渡到企业环境

如果你更关心的是：

- 本地快速起步
- 私有知识库
- 低成本运行
- 基于现有仓库继续改造

那 RAGBox 的优势会比较明显。

---

## 一键安装

### 环境要求

- Python 3.10+
- Node.js 20+
- npm 10+

### 安装命令

```bash
git clone https://github.com/tavisWei/RAGBox.git
cd RAGBox
./install.sh
```

### 安装脚本会做什么

`./install.sh` 会自动完成：

- 创建 Python 虚拟环境
- 安装后端依赖
- 安装前端依赖
- 初始化本地运行目录

也就是说，**不需要手动一项一项装环境**。

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

如果你已经启动过服务，想直接重启，使用：

```bash
./restart.sh
```

`restart.sh` 会：

- 停掉当前占用后端端口和前端端口的进程
- 然后重新执行 `start.sh`

默认处理的端口是：

- 后端：`8000`
- 前端：`3003`

如果你自定义了环境变量 `API_PORT` / `WEB_PORT`，重启脚本也会跟着使用同样的端口。

### 更新

拉取最新代码后，重新执行安装脚本即可：

```bash
git pull
./install.sh
./restart.sh
```

这是最适合日常更新的方式。

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

### 技术架构说明

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

你可以把它理解成：

**一个已经具备基本产品形态、适合继续工程化和业务化扩展的 RAG 私有知识问答项目。**

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

如果你想继续深入，可以看这些文档：

- [开发指南](docs/development-guide.md)
- [部署指南](docs/deployment-guide.md)
- [API 文档](docs/api-documentation.md)
- [技术架构文档](deliverables/architecture/technical-architecture.md)

---

## License

Apache License 2.0

---

如果这个项目对你有帮助，欢迎 Star。
