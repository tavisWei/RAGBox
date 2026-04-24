# Development Guide

This guide covers how to set up the development environment, run tests, and contribute to the RAG Platform project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setting Up the Development Environment](#setting-up-the-development-environment)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Architecture Overview](#architecture-overview)
- [Adding a New Data Store Backend](#adding-a-new-data-store-backend)
- [Frontend Development](#frontend-development)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.10 or higher
- Node.js 20 or higher
- npm 10 or higher
- Git

## Project Structure

```
rag-platform/
├── api/                          # Python backend
│   ├── api/                      # FastAPI route modules
│   ├── core/
│   │   └── rag/
│   │       ├── datasource/
│   │       │   └── unified/      # Unified data layer
│   │       │       ├── base_data_store.py
│   │       │       ├── sqlite_data_store.py
│   │       │       ├── pgvector_data_store.py
│   │       │       ├── elasticsearch_data_store.py
│   │       │       ├── data_store_factory.py
│   │       │       └── tests/
│   │       └── retrieval/        # Enhanced retrieval engine
│   │           ├── multi_way_retriever.py
│   │           ├── fusion_strategies.py
│   │           └── reranker.py
│   ├── services/
│   ├── tests/
│   └── data/                     # Local runtime data (gitignored)
├── web-vue/                      # Vue 3 + Vite frontend
│   ├── src/
│   │   ├── views/
│   │   ├── components/
│   │   ├── stores/
│   │   └── router/
│   └── package.json
├── docs/                         # Documentation
├── deliverables/                 # Design documents
├── scripts/                      # Utility scripts
├── install.sh
└── start.sh
```

## Setting Up the Development Environment

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/rag-platform.git
cd rag-platform
```

### 2. Install Dependencies

```bash
./install.sh
```

### 3. Activate the Virtual Environment

```bash
source .venv/bin/activate
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
DATA_STORE_TYPE=sqlite
SQLITE_DB_PATH=api/data/rag.sqlite
```

For pgvector development:

```bash
PGVECTOR_HOST=localhost
PGVECTOR_PORT=5432
PGVECTOR_DATABASE=rag_platform
PGVECTOR_USER=postgres
PGVECTOR_PASSWORD=password
```

For Elasticsearch development:

```bash
ELASTICSEARCH_HOSTS=http://localhost:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=<set-secure-password>
```

## Running Tests

### Run All Tests

```bash
python -m pytest api/ -v
```

### Run Specific Test Files

```bash
python -m pytest api/tests/test_api.py -v
python -m pytest api/tests/test_integration.py -v
python -m pytest api/tests/test_workflows.py -v
python -m pytest api/core/rag/datasource/unified/tests/test_unified_data_store.py -v
python -m pytest api/core/rag/datasource/unified/tests/test_phase2_data_stores.py -v
python -m pytest api/core/rag/datasource/unified/tests/test_phase2_resource_config.py -v
```

### Run with Coverage

```bash
python -m pytest api/ --cov=api --cov-report=html --cov-report=term
```

### Frontend Validation

```bash
cd web-vue
npm run build
npm run lint
```

## Code Style

### Python

We use the following tools:

- **Black** for code formatting
- **Flake8** for linting
- **MyPy** for type checking

Run all checks:

```bash
black api/
flake8 api/
mypy api/
```

### TypeScript

```bash
cd web-vue
npm run lint
npm run format
```

## Architecture Overview

### Unified Data Layer

The unified data layer provides a single interface for multiple storage backends:

```
┌─────────────────────────────────────────┐
│         BaseDataStore (ABC)             │
│  - create_collection()                  │
│  - add_documents()                      │
│  - search()                             │
│  - delete_documents()                   │
│  - delete_collection()                  │
│  - get_stats()                          │
│  - health_check()                       │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐   ┌─────▼─────┐   ┌────▼─────┐
│ SQLite │   │  PGVector │   │    ES    │
│ + FTS5 │   │  + HNSW   │   │  Cluster │
└────────┘   └───────────┘   └──────────┘
```

### Retrieval Engine

```
┌─────────────────────────────────────────┐
│       MultiWayRetriever                 │
│  - Parallel vector + keyword search     │
│  - Fusion (RRF / Weighted)              │
│  - Optional reranking                   │
└─────────────────────────────────────────┘
```

### Resource Configuration

Three resource levels map to different backends:

| Level | Backend | Use Case |
|-------|---------|----------|
| Low | SQLite + FTS5 | Personal, small team |
| Medium | PostgreSQL + pgvector | SMB, self-hosted |
| High | Elasticsearch cluster | Enterprise, scale |

## Adding a New Data Store Backend

To add a new backend (for example, Milvus):

1. Create a new file: `api/core/rag/datasource/unified/milvus_data_store.py`

2. Implement the `BaseDataStore` interface:

```python
from api.core.rag.datasource.unified.base_data_store import BaseDataStore, Document, SearchResult, DataStoreStats

class MilvusDataStore(BaseDataStore):
    def _get_backend_type(self) -> str:
        return "milvus"

    def create_collection(self, collection_name: str, dimension: Optional[int] = None) -> None:
        ...

    def add_documents(self, collection_name: str, documents: List[Document], embeddings: Optional[List[List[float]]] = None) -> List[str]:
        ...

    def search(self, collection_name: str, query: str, query_vector: Optional[List[float]] = None, top_k: int = 10, score_threshold: float = 0.0, filters: Optional[Dict[str, Any]] = None, search_method: str = "hybrid") -> List[SearchResult]:
        ...

    def delete_documents(self, collection_name: str, doc_ids: List[str]) -> None:
        ...

    def delete_collection(self, collection_name: str) -> None:
        ...

    def get_stats(self, collection_name: str) -> DataStoreStats:
        ...

    def health_check(self) -> bool:
        ...
```

3. Register in the factory:

```python
# In api/core/rag/datasource/unified/data_store_factory.py
from .milvus_data_store import MilvusDataStore

class DataStoreFactory:
    _registry = {
        "sqlite": SQLiteDataStore,
        "milvus": MilvusDataStore,
    }
```

4. Add tests in `api/core/rag/datasource/unified/tests/`

5. Update documentation

## Frontend Development

### Starting the Development Server

```bash
cd web-vue
npm run dev
```

The frontend will be available at `http://localhost:3003` when started via `../start.sh`.

### Key Frontend Components

| Component | Path | Purpose |
|-----------|------|---------|
| ResourceConfigView | `web-vue/src/views/ResourceConfigView.vue` | Resource configuration management |
| MonitoringView | `web-vue/src/views/MonitoringView.vue` | System metrics and health dashboards |
| KnowledgeBaseView | `web-vue/src/views/KnowledgeBaseView.vue` | Knowledge base list and entry point |
| Router | `web-vue/src/router/index.ts` | Frontend route registration |

### Adding a New Page

1. Create a new view under `web-vue/src/views/`
2. Register the route in `web-vue/src/router/index.ts`
3. Update navigation or menus if needed

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError` for `api.*` modules, ensure you run tests from the project root and have a `pytest.ini` with:

```ini
[pytest]
pythonpath = .
```

### SQLite FTS5 Not Available

On some systems, SQLite may be compiled without FTS5. Check with:

```python
import sqlite3
print(sqlite3.sqlite_version)
```

FTS5 requires SQLite 3.9.0 or higher.

### Mock Module Issues

When testing with mocked external dependencies (psycopg2, elasticsearch), ensure mock modules are injected into `sys.modules` before import:

```python
import sys
sys.modules["elasticsearch"] = MockElasticsearchModule()
```

### Frontend Build Errors

If you see "Cannot find module" errors, run:

```bash
cd web-vue
rm -rf node_modules package-lock.json
npm install
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests
4. Run the full test suite
5. Submit a pull request

All contributions should include tests and follow the existing code style.
