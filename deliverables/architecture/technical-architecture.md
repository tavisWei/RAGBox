# 技术架构设计文档

## 1. 架构概述

### 1.1 设计原则
- **配置驱动**：通过 YAML/环境变量切换后端，零代码修改
- **接口先行**：定义 `BaseDataStore` 抽象，所有后端实现统一接口
- **渐进增强**：从简单方案开始，根据需求逐步升级
- **最小侵入**：保持 Dify 现有架构完整，通过扩展点增强

### 1.2 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Presentation (React + shadcn/ui)                  │
│  - 资源适配配置页面                                          │
│  - 知识库管理增强                                            │
│  - 系统监控面板                                              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: API Gateway (Flask/FastAPI)                       │
│  - Dify 现有 API 路由                                        │
│  - 新增 /api/resource-configs/*                              │
│  - 新增 /api/monitoring/*                                    │
│  - 扩展 /api/datasets/* (resource_level 参数)               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Business Logic                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Resource Config Service                            │    │
│  │  - 配置 CRUD                                        │    │
│  │  - 级别切换逻辑                                      │    │
│  │  - 默认配置管理                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Unified Data Layer                                 │    │
│  │  - BaseDataStore 抽象                               │    │
│  │  - 后端工厂模式                                      │    │
│  │  - 自动后端选择                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Enhanced Retrieval Engine                          │    │
│  │  - 多路召回调度                                      │    │
│  │  - 融合策略 (RRF/Weighted)                          │    │
│  │  - 重排序集成                                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Data Access (Pluggable Adapters)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  SQLite  │ │PGVector  │ │   ES     │ │   External   │  │
│  │  + FTS5  │ │+tsvector │ │  Cluster │ │    API       │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: Infrastructure                                    │
│  - Docker / Docker Compose                                   │
│  - PostgreSQL (Dify 默认)                                    │
│  - Redis (Dify 默认)                                         │
│  - 可选: Elasticsearch / Milvus / Qdrant                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心组件详细设计

### 2.1 BaseDataStore 抽象层

```python
# core/rag/datasource/unified/base_data_store.py

from abc import ABC, abstractmethod
from typing import Any, TypedDict
from dataclasses import dataclass
from core.rag.models.document import Document


@dataclass
class SearchResult:
    """统一搜索结果"""
    content: str
    score: float
    doc_id: str
    metadata: dict[str, Any]
    retrieval_method: str  # "vector" | "keyword" | "fulltext"


@dataclass
class DataStoreStats:
    """存储统计信息"""
    total_documents: int
    total_chunks: int
    index_size_bytes: int
    avg_query_latency_ms: float
    backend_type: str


class BaseDataStore(ABC):
    """
    统一数据层抽象基类
    
    所有存储后端（SQLite、PostgreSQL、Elasticsearch等）必须实现此接口。
    提供统一的文档存储和检索能力，屏蔽底层差异。
    """
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.backend_type = self._get_backend_type()
    
    @abstractmethod
    def _get_backend_type(self) -> str:
        """返回后端类型标识"""
        raise NotImplementedError
    
    @abstractmethod
    def create_collection(self, collection_name: str, dimension: int | None = None) -> None:
        """
        创建集合/表/索引
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度（仅向量存储需要）
        """
        raise NotImplementedError
    
    @abstractmethod
    def add_documents(
        self, 
        collection_name: str,
        documents: list[Document], 
        embeddings: list[list[float]] | None = None
    ) -> list[str]:
        """
        添加文档
        
        Args:
            collection_name: 目标集合
            documents: 文档列表
            embeddings: 可选的预计算向量
            
        Returns:
            文档ID列表
        """
        raise NotImplementedError
    
    @abstractmethod
    def search(
        self,
        collection_name: str,
        query: str,
        query_vector: list[float] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        search_method: str = "hybrid"  # "semantic" | "keyword" | "fulltext" | "hybrid"
    ) -> list[SearchResult]:
        """
        统一检索接口
        
        Args:
            collection_name: 目标集合
            query: 查询文本
            query_vector: 可选的查询向量
            top_k: 返回结果数
            score_threshold: 分数阈值
            filters: 元数据过滤条件
            search_method: 检索方法
            
        Returns:
            搜索结果列表
        """
        raise NotImplementedError
    
    @abstractmethod
    def delete_documents(self, collection_name: str, doc_ids: list[str]) -> None:
        """删除文档"""
        raise NotImplementedError
    
    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """删除集合"""
        raise NotImplementedError
    
    @abstractmethod
    def get_stats(self, collection_name: str) -> DataStoreStats:
        """获取存储统计"""
        raise NotImplementedError
    
    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        raise NotImplementedError
```

### 2.2 数据存储工厂

```python
# core/rag/datasource/unified/data_store_factory.py

import os
from typing import Any
from configs import dify_config
from .base_data_store import BaseDataStore
from .sqlite_data_store import SQLiteDataStore
from .pgvector_data_store import PGVectorDataStore
from .elasticsearch_data_store import ElasticsearchDataStore


class DataStoreFactory:
    """数据存储工厂"""
    
    _registry: dict[str, type[BaseDataStore]] = {
        "sqlite": SQLiteDataStore,
        "pgvector": PGVectorDataStore,
        "elasticsearch": ElasticsearchDataStore,
    }
    
    @classmethod
    def register(cls, name: str, store_class: type[BaseDataStore]) -> None:
        """注册新的存储后端"""
        cls._registry[name] = store_class
    
    @classmethod
    def create(cls, store_type: str | None = None, config: dict[str, Any] | None = None) -> BaseDataStore:
        """
        创建数据存储实例
        
        优先级：
        1. 传入的 store_type 参数
        2. 环境变量 DATA_STORE_TYPE
        3. Dify 配置 VECTOR_STORE
        4. 默认 "pgvector"
        """
        store_type = store_type or os.getenv("DATA_STORE_TYPE") or dify_config.VECTOR_STORE or "pgvector"
        
        if store_type not in cls._registry:
            raise ValueError(f"Unknown data store type: {store_type}. "
                           f"Available: {list(cls._registry.keys())}")
        
        store_class = cls._registry[store_type]
        return store_class(config or {})
    
    @classmethod
    def get_available_stores(cls) -> list[str]:
        """获取所有可用的存储类型"""
        return list(cls._registry.keys())
```

### 2.3 资源配置服务

```python
# services/resource_config_service.py

from enum import Enum
from typing import Any
from models.resource_config import ResourceConfig, ResourceLevel


class ResourceConfigService:
    """资源配置服务"""
    
    # 预定义的默认配置
    DEFAULT_CONFIGS = {
        ResourceLevel.LOW: {
            "data_store_type": "sqlite",
            "vector_enabled": False,
            "keyword_enabled": True,
            "fulltext_enabled": True,
            "hybrid_fusion_method": "rrf",
            "rerank_enabled": False,
            "max_documents": 10000,
            "embedding_model": "text-embedding-3-small",
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
        ResourceLevel.MEDIUM: {
            "data_store_type": "pgvector",
            "vector_enabled": True,
            "keyword_enabled": True,
            "fulltext_enabled": True,
            "hybrid_fusion_method": "rrf",
            "rerank_enabled": True,
            "max_documents": 1000000,
            "embedding_model": "text-embedding-3-small",
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
        ResourceLevel.HIGH: {
            "data_store_type": "elasticsearch",
            "vector_enabled": True,
            "keyword_enabled": True,
            "fulltext_enabled": True,
            "hybrid_fusion_method": "rrf",
            "rerank_enabled": True,
            "max_documents": 100000000,
            "embedding_model": "text-embedding-3-large",
            "chunk_size": 1000,
            "chunk_overlap": 100,
        },
    }
    
    @classmethod
    def get_default_config(cls, level: ResourceLevel) -> dict[str, Any]:
        """获取指定级别的默认配置"""
        return cls.DEFAULT_CONFIGS.get(level, cls.DEFAULT_CONFIGS[ResourceLevel.MEDIUM]).copy()
    
    @classmethod
    def create_config(
        cls, 
        tenant_id: str, 
        level: ResourceLevel, 
        custom_config: dict[str, Any] | None = None
    ) -> ResourceConfig:
        """创建资源配置"""
        config = cls.get_default_config(level)
        if custom_config:
            config.update(custom_config)
        
        return ResourceConfig(
            tenant_id=tenant_id,
            level=level,
            data_store_type=config["data_store_type"],
            config_json=config,
            is_default=False
        )
    
    @classmethod
    def get_config_for_dataset(cls, dataset_id: str) -> ResourceConfig:
        """获取知识库对应的资源配置"""
        # 1. 查询知识库绑定的配置
        binding = DatasetResourceBinding.query.filter_by(dataset_id=dataset_id).first()
        if binding and binding.resource_config:
            return binding.resource_config
        
        # 2. 返回租户默认配置
        # TODO: 从当前租户获取
        return ResourceConfig.query.filter_by(is_default=True).first()
```

---

## 3. 后端适配器实现

### 3.1 SQLite + FTS5 适配器（低资源）

```python
# core/rag/datasource/unified/sqlite_data_store.py

import sqlite3
import json
import numpy as np
from typing import Any
from .base_data_store import BaseDataStore, SearchResult, DataStoreStats
from core.rag.models.document import Document


class SQLiteDataStore(BaseDataStore):
    """
    SQLite + FTS5 数据存储适配器
    
    适用于低资源场景，单文件存储，零配置。
    支持全文检索（FTS5），可选向量存储（使用 numpy 计算余弦相似度）。
    """
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "data/rag_data.db")
        self.vector_enabled = config.get("vector_enabled", False)
        self._init_db()
    
    def _get_backend_type(self) -> str:
        return "sqlite"
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            # 启用 FTS5
            conn.execute("PRAGMA foreign_keys = ON")
            
            # 文档表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 向量表（可选）
            if self.vector_enabled:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vectors (
                        doc_id TEXT PRIMARY KEY,
                        embedding BLOB,
                        FOREIGN KEY (doc_id) REFERENCES documents(id)
                    )
                """)
    
    def create_collection(self, collection_name: str, dimension: int | None = None) -> None:
        """创建 FTS5 虚拟表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {collection_name}_fts 
                USING fts5(content, content_rowid=rowid)
            """)
    
    def add_documents(
        self, 
        collection_name: str,
        documents: list[Document], 
        embeddings: list[list[float]] | None = None
    ) -> list[str]:
        """添加文档"""
        doc_ids = []
        with sqlite3.connect(self.db_path) as conn:
            for i, doc in enumerate(documents):
                doc_id = doc.metadata.get("doc_id", str(uuid.uuid4()))
                doc_ids.append(doc_id)
                
                # 插入文档
                conn.execute(
                    "INSERT OR REPLACE INTO documents (id, content, metadata) VALUES (?, ?, ?)",
                    (doc_id, doc.page_content, json.dumps(doc.metadata))
                )
                
                # 插入 FTS 索引
                conn.execute(
                    f"INSERT INTO {collection_name}_fts (content) VALUES (?)",
                    (doc.page_content,)
                )
                
                # 插入向量（如果启用）
                if self.vector_enabled and embeddings:
                    embedding_blob = np.array(embeddings[i], dtype=np.float32).tobytes()
                    conn.execute(
                        "INSERT OR REPLACE INTO vectors (doc_id, embedding) VALUES (?, ?)",
                        (doc_id, embedding_blob)
                    )
            
            conn.commit()
        
        return doc_ids
    
    def search(
        self,
        collection_name: str,
        query: str,
        query_vector: list[float] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        search_method: str = "hybrid"
    ) -> list[SearchResult]:
        """检索文档"""
        results = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # FTS5 全文检索
            if search_method in ["keyword", "fulltext", "hybrid"]:
                cursor = conn.execute(f"""
                    SELECT d.id, d.content, d.metadata, rank
                    FROM {collection_name}_fts fts
                    JOIN documents d ON fts.rowid = d.rowid
                    WHERE {collection_name}_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, top_k))
                
                for row in cursor:
                    results.append(SearchResult(
                        content=row["content"],
                        score=self._normalize_score(row["rank"]),
                        doc_id=row["id"],
                        metadata=json.loads(row["metadata"] or "{}"),
                        retrieval_method="fulltext"
                    ))
            
            # 向量检索（如果启用）
            if self.vector_enabled and search_method in ["semantic", "hybrid"] and query_vector:
                vector_results = self._vector_search(conn, query_vector, top_k)
                results.extend(vector_results)
        
        # 去重和排序
        return self._deduplicate_and_sort(results, top_k)
    
    def _vector_search(self, conn, query_vector: list[float], top_k: int) -> list[SearchResult]:
        """向量相似度搜索"""
        query_vec = np.array(query_vector, dtype=np.float32)
        results = []
        
        cursor = conn.execute("SELECT doc_id, embedding FROM vectors")
        for row in cursor:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            similarity = np.dot(query_vec, embedding) / (np.linalg.norm(query_vec) * np.linalg.norm(embedding))
            
            # 获取文档内容
            doc_cursor = conn.execute(
                "SELECT content, metadata FROM documents WHERE id = ?", 
                (row["doc_id"],)
            )
            doc = doc_cursor.fetchone()
            
            if doc:
                results.append(SearchResult(
                    content=doc["content"],
                    score=float(similarity),
                    doc_id=row["doc_id"],
                    metadata=json.loads(doc["metadata"] or "{}"),
                    retrieval_method="vector"
                ))
        
        # 按相似度排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def _normalize_score(self, rank: float) -> float:
        """归一化 FTS5 rank 分数"""
        # FTS5 rank 是负数，越小越相关
        return min(1.0, max(0.0, 1.0 / (1.0 + abs(rank))))
    
    def _deduplicate_and_sort(self, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        """去重并排序"""
        seen = set()
        unique_results = []
        for r in results:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                unique_results.append(r)
        
        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:top_k]
    
    def delete_documents(self, collection_name: str, doc_ids: list[str]) -> None:
        """删除文档"""
        with sqlite3.connect(self.db_path) as conn:
            for doc_id in doc_ids:
                conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.execute("DELETE FROM vectors WHERE doc_id = ?", (doc_id,))
            conn.commit()
    
    def delete_collection(self, collection_name: str) -> None:
        """删除集合"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {collection_name}_fts")
            conn.commit()
    
    def get_stats(self, collection_name: str) -> DataStoreStats:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]
            
            cursor = conn.execute(f"SELECT COUNT(*) FROM {collection_name}_fts")
            total_chunks = cursor.fetchone()[0]
            
            return DataStoreStats(
                total_documents=total_docs,
                total_chunks=total_chunks,
                index_size_bytes=0,  # TODO: 计算文件大小
                avg_query_latency_ms=0.0,  # TODO: 从监控获取
                backend_type="sqlite"
            )
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
```

### 3.2 PostgreSQL + pgvector 适配器（中资源）

```python
# core/rag/datasource/unified/pgvector_data_store.py

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any
from .base_data_store import BaseDataStore, SearchResult, DataStoreStats
from core.rag.models.document import Document


class PGVectorDataStore(BaseDataStore):
    """
    PostgreSQL + pgvector 数据存储适配器
    
    适用于中等资源场景，支持向量检索和全文检索。
    使用 pgvector 扩展存储向量，使用 PostgreSQL tsvector 进行全文检索。
    """
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.user = config.get("user", "postgres")
        self.password = config.get("password", "")
        self.database = config.get("database", "dify")
        self._init_extensions()
    
    def _get_backend_type(self) -> str:
        return "pgvector"
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database
        )
    
    def _init_extensions(self):
        """初始化扩展"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 启用 pgvector
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                conn.commit()
    
    def create_collection(self, collection_name: str, dimension: int | None = None) -> None:
        """创建表和索引"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 创建文档表
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {collection_name}_docs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        content TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector({dimension}) {"IF dimension ELSE "vector(1536)"}
                        ,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建全文检索索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{collection_name}_fts 
                    ON {collection_name}_docs 
                    USING gin(to_tsvector('simple', content))
                """)
                
                # 创建向量索引（HNSW）
                if dimension:
                    cur.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_{collection_name}_vector 
                        ON {collection_name}_docs 
                        USING hnsw(embedding vector_cosine_ops)
                    """)
                
                conn.commit()
    
    def add_documents(
        self, 
        collection_name: str,
        documents: list[Document], 
        embeddings: list[list[float]] | None = None
    ) -> list[str]:
        """添加文档"""
        doc_ids = []
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                for i, doc in enumerate(documents):
                    doc_id = doc.metadata.get("doc_id")
                    embedding = embeddings[i] if embeddings else None
                    
                    cur.execute(f"""
                        INSERT INTO {collection_name}_docs (id, content, metadata, embedding)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (
                        doc_id,
                        doc.page_content,
                        json.dumps(doc.metadata),
                        embedding
                    ))
                    
                    result = cur.fetchone()
                    doc_ids.append(result[0])
                
                conn.commit()
        
        return doc_ids
    
    def search(
        self,
        collection_name: str,
        query: str,
        query_vector: list[float] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        search_method: str = "hybrid"
    ) -> list[SearchResult]:
        """检索文档"""
        results = []
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 全文检索
                if search_method in ["keyword", "fulltext", "hybrid"]:
                    cur.execute(f"""
                        SELECT 
                            id,
                            content,
                            metadata,
                            ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', %s)) as score
                        FROM {collection_name}_docs
                        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
                        ORDER BY score DESC
                        LIMIT %s
                    """, (query, query, top_k))
                    
                    for row in cur:
                        results.append(SearchResult(
                            content=row["content"],
                            score=row["score"],
                            doc_id=str(row["id"]),
                            metadata=row["metadata"] or {},
                            retrieval_method="fulltext"
                        ))
                
                # 向量检索
                if search_method in ["semantic", "hybrid"] and query_vector:
                    cur.execute(f"""
                        SELECT 
                            id,
                            content,
                            metadata,
                            1 - (embedding <=> %s::vector) as score
                        FROM {collection_name}_docs
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (query_vector, query_vector, top_k))
                    
                    for row in cur:
                        results.append(SearchResult(
                            content=row["content"],
                            score=row["score"],
                            doc_id=str(row["id"]),
                            metadata=row["metadata"] or {},
                            retrieval_method="vector"
                        ))
        
        # 去重和排序
        return self._deduplicate_and_sort(results, top_k)
    
    def delete_documents(self, collection_name: str, doc_ids: list[str]) -> None:
        """删除文档"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    f"DELETE FROM {collection_name}_docs WHERE id = %s",
                    [(doc_id,) for doc_id in doc_ids]
                )
                conn.commit()
    
    def delete_collection(self, collection_name: str) -> None:
        """删除集合"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {collection_name}_docs")
                conn.commit()
    
    def get_stats(self, collection_name: str) -> DataStoreStats:
        """获取统计信息"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {collection_name}_docs")
                total_docs = cur.fetchone()[0]
                
                return DataStoreStats(
                    total_documents=total_docs,
                    total_chunks=total_docs,
                    index_size_bytes=0,
                    avg_query_latency_ms=0.0,
                    backend_type="pgvector"
                )
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False
```

### 3.3 Elasticsearch 适配器（高资源）

```python
# core/rag/datasource/unified/elasticsearch_data_store.py

from elasticsearch import Elasticsearch
from typing import Any
from .base_data_store import BaseDataStore, SearchResult, DataStoreStats
from core.rag.models.document import Document


class ElasticsearchDataStore(BaseDataStore):
    """
    Elasticsearch 数据存储适配器
    
    适用于高资源场景，支持原生混合检索（BM25 + 向量）。
    使用 Elasticsearch 的 dense_vector 和 text 字段实现统一存储和检索。
    """
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.hosts = config.get("hosts", ["http://localhost:9200"])
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.es = Elasticsearch(
            hosts=self.hosts,
            basic_auth=(self.username, self.password) if self.username else None
        )
    
    def _get_backend_type(self) -> str:
        return "elasticsearch"
    
    def create_collection(self, collection_name: str, dimension: int | None = 1536) -> None:
        """创建索引"""
        mapping = {
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "metadata": {
                        "type": "object"
                    },
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dimension,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "created_at": {
                        "type": "date"
                    }
                }
            }
        }
        
        if not self.es.indices.exists(index=collection_name):
            self.es.indices.create(index=collection_name, body=mapping)
    
    def add_documents(
        self, 
        collection_name: str,
        documents: list[Document], 
        embeddings: list[list[float]] | None = None
    ) -> list[str]:
        """添加文档"""
        doc_ids = []
        
        for i, doc in enumerate(documents):
            doc_id = doc.metadata.get("doc_id", str(uuid.uuid4()))
            doc_ids.append(doc_id)
            
            body = {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "created_at": datetime.now().isoformat()
            }
            
            if embeddings:
                body["embedding"] = embeddings[i]
            
            self.es.index(index=collection_name, id=doc_id, body=body)
        
        self.es.indices.refresh(index=collection_name)
        return doc_ids
    
    def search(
        self,
        collection_name: str,
        query: str,
        query_vector: list[float] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        search_method: str = "hybrid"
    ) -> list[SearchResult]:
        """检索文档"""
        
        if search_method == "semantic" and query_vector:
            # 纯向量检索
            return self._vector_search(collection_name, query_vector, top_k, score_threshold)
        
        elif search_method == "fulltext":
            # 纯全文检索
            return self._fulltext_search(collection_name, query, top_k, score_threshold)
        
        elif search_method == "hybrid" and query_vector:
            # 混合检索：使用 ES 的 hybrid search
            return self._hybrid_search(collection_name, query, query_vector, top_k, score_threshold)
        
        else:
            # 默认全文检索
            return self._fulltext_search(collection_name, query, top_k, score_threshold)
    
    def _vector_search(self, index, query_vector, top_k, score_threshold):
        """向量检索"""
        response = self.es.search(
            index=index,
            body={
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 2
                }
            }
        )
        
        return self._parse_results(response, "vector")
    
    def _fulltext_search(self, index, query, top_k, score_threshold):
        """全文检索"""
        response = self.es.search(
            index=index,
            body={
                "query": {
                    "match": {
                        "content": query
                    }
                },
                "size": top_k
            }
        )
        
        return self._parse_results(response, "fulltext")
    
    def _hybrid_search(self, index, query, query_vector, top_k, score_threshold):
        """混合检索（RRF）"""
        response = self.es.search(
            index=index,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "content": query
                                }
                            }
                        ]
                    }
                },
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 2
                },
                "rank": {
                    "rrf": {
                        "window_size": top_k * 2,
                        "rank_constant": 60
                    }
                },
                "size": top_k
            }
        )
        
        return self._parse_results(response, "hybrid")
    
    def _parse_results(self, response, retrieval_method):
        """解析 ES 响应"""
        results = []
        for hit in response["hits"]["hits"]:
            results.append(SearchResult(
                content=hit["_source"]["content"],
                score=hit["_score"],
                doc_id=hit["_id"],
                metadata=hit["_source"].get("metadata", {}),
                retrieval_method=retrieval_method
            ))
        return results
    
    def delete_documents(self, collection_name: str, doc_ids: list[str]) -> None:
        """删除文档"""
        for doc_id in doc_ids:
            self.es.delete(index=collection_name, id=doc_id)
    
    def delete_collection(self, collection_name: str) -> None:
        """删除索引"""
        self.es.indices.delete(index=collection_name, ignore=[404])
    
    def get_stats(self, collection_name: str) -> DataStoreStats:
        """获取统计信息"""
        stats = self.es.indices.stats(index=collection_name)
        
        return DataStoreStats(
            total_documents=stats["indices"][collection_name]["total"]["docs"]["count"],
            total_chunks=stats["indices"][collection_name]["total"]["docs"]["count"],
            index_size_bytes=stats["indices"][collection_name]["total"]["store"]["size_in_bytes"],
            avg_query_latency_ms=0.0,
            backend_type="elasticsearch"
        )
    
    def health_check(self) -> bool:
        """健康检查"""
        return self.es.ping()
```

---

## 4. 与 Dify 集成方案

### 4.1 集成点分析

| Dify 组件 | 集成方式 | 修改范围 |
|-----------|----------|----------|
| `BaseVector` | 新增 `UnifiedDataStoreVector` 适配器 | 新增文件 |
| `BaseKeyword` | 新增 `UnifiedDataStoreKeyword` 适配器 | 新增文件 |
| `RetrievalService` | 扩展 `_retrieve` 方法，支持统一数据层 | 修改方法 |
| `IndexingRunner` | 扩展索引流程，根据资源级别选择后端 | 修改方法 |
| `Dataset` 模型 | 新增 `resource_level` 字段 | 新增字段 |
| Frontend | 新增配置页面和监控面板 | 新增页面 |

### 4.2 最小侵入集成策略

```python
# core/rag/datasource/vdb/unified_vector_adapter.py

"""
Dify BaseVector 的统一数据层适配器

将 BaseDataStore 包装为 Dify 的 BaseVector 接口，
实现与 Dify 现有代码的无缝集成。
"""

from core.rag.datasource.vdb.vector_base import BaseVector
from core.rag.datasource.unified.data_store_factory import DataStoreFactory
from core.services.resource_config_service import ResourceConfigService


class UnifiedVectorAdapter(BaseVector):
    """
    统一数据层向量适配器
    
    包装 BaseDataStore，使其符合 Dify 的 BaseVector 接口。
    """
    
    def __init__(self, collection_name: str, dataset: Dataset):
        super().__init__(collection_name)
        self.dataset = dataset
        
        # 获取知识库的资源配置
        config = ResourceConfigService.get_config_for_dataset(dataset.id)
        
        # 创建对应的数据存储实例
        self.data_store = DataStoreFactory.create(
            store_type=config.data_store_type,
            config=config.config_json
        )
        
        # 确保集合存在
        self.data_store.create_collection(collection_name)
    
    def get_type(self) -> str:
        return f"unified_{self.data_store.backend_type}"
    
    def create(self, texts, embeddings, **kwargs):
        self.data_store.add_documents(self.collection_name, texts, embeddings)
    
    def add_texts(self, documents, embeddings, **kwargs):
        self.data_store.add_documents(self.collection_name, documents, embeddings)
    
    def search_by_vector(self, query_vector, **kwargs):
        results = self.data_store.search(
            self.collection_name,
            query="",
            query_vector=query_vector,
            top_k=kwargs.get("top_k", 10),
            search_method="semantic"
        )
        return [self._to_document(r) for r in results]
    
    def search_by_full_text(self, query, **kwargs):
        results = self.data_store.search(
            self.collection_name,
            query=query,
            top_k=kwargs.get("top_k", 10),
            search_method="fulltext"
        )
        return [self._to_document(r) for r in results]
    
    def delete_by_ids(self, ids):
        self.data_store.delete_documents(self.collection_name, ids)
    
    def delete(self):
        self.data_store.delete_collection(self.collection_name)
    
    def _to_document(self, result):
        """转换为 Dify Document 对象"""
        return Document(
            page_content=result.content,
            metadata={
                **result.metadata,
                "score": result.score,
                "doc_id": result.doc_id
            }
        )
```

### 4.3 配置注册

```python
# 在 vector_backend_registry.py 中注册

from core.rag.datasource.vdb.unified_vector_adapter import UnifiedVectorAdapter

# 注册统一数据层适配器
register_vector_backend("unified", UnifiedVectorAdapter)
```

---

## 5. 部署架构

### 5.1 低资源部署（单机）

```yaml
# docker-compose.low.yml
version: '3'
services:
  dify-api:
    image: dify-api:latest
    environment:
      - DATA_STORE_TYPE=sqlite
      - SQLITE_DB_PATH=/app/data/rag.db
    volumes:
      - ./data:/app/data
    
  dify-web:
    image: dify-web:latest
    ports:
      - "3000:3000"
    
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=dify
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=difyai123456
    volumes:
      - ./pgdata:/var/lib/postgresql/data
```

### 5.2 中资源部署（标准）

```yaml
# docker-compose.medium.yml
version: '3'
services:
  dify-api:
    image: dify-api:latest
    environment:
      - DATA_STORE_TYPE=pgvector
      - PGVECTOR_HOST=postgres
      - PGVECTOR_PORT=5432
    
  dify-web:
    image: dify-web:latest
    ports:
      - "3000:3000"
    
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=dify
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=difyai123456
    volumes:
      - ./pgdata:/var/lib/postgresql/data
    
  redis:
    image: redis:6-alpine
    volumes:
      - ./redisdata:/data
```

### 5.3 高资源部署（集群）

```yaml
# docker-compose.high.yml
version: '3'
services:
  dify-api:
    image: dify-api:latest
    environment:
      - DATA_STORE_TYPE=elasticsearch
      - ELASTICSEARCH_HOSTS=http://es01:9200,http://es02:9200,http://es03:9200
    deploy:
      replicas: 3
    
  dify-web:
    image: dify-web:latest
    ports:
      - "3000:3000"
    deploy:
      replicas: 2
    
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=dify
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=difyai123456
    volumes:
      - ./pgdata:/var/lib/postgresql/data
    
  es01:
    image: elasticsearch:8.11.0
    environment:
      - node.name=es01
      - cluster.name=es-cluster
      - discovery.seed_hosts=es02,es03
      - cluster.initial_master_nodes=es01,es02,es03
    volumes:
      - ./esdata01:/usr/share/elasticsearch/data
    
  es02:
    image: elasticsearch:8.11.0
    environment:
      - node.name=es02
      - cluster.name=es-cluster
      - discovery.seed_hosts=es01,es03
      - cluster.initial_master_nodes=es01,es02,es03
    volumes:
      - ./esdata02:/usr/share/elasticsearch/data
    
  es03:
    image: elasticsearch:8.11.0
    environment:
      - node.name=es03
      - cluster.name=es-cluster
      - discovery.seed_hosts=es01,es02
      - cluster.initial_master_nodes=es01,es02,es03
    volumes:
      - ./esdata03:/usr/share/elasticsearch/data
    
  redis:
    image: redis:6-alpine
    volumes:
      - ./redisdata:/data
```

---

## 6. 监控与可观测性

### 6.1 关键指标

| 指标 | 类型 | 说明 |
|------|------|------|
| retrieval_latency_ms | Histogram | 检索延迟分布 |
| retrieval_qps | Counter | 检索 QPS |
| index_build_time_seconds | Gauge | 索引构建时间 |
| data_store_health | Gauge | 存储后端健康状态 |
| document_count | Gauge | 文档数量 |

### 6.2 健康检查端点

```python
# api/health.py

@app.route('/health')
def health_check():
    """系统健康检查"""
    checks = {
        "api": True,
        "database": check_database(),
        "data_store": check_data_store(),
        "redis": check_redis()
    }
    
    status = 200 if all(checks.values()) else 503
    return jsonify({"status": "healthy" if status == 200 else "unhealthy", "checks": checks}), status
```

---

## 7. 安全设计

### 7.1 数据隔离
- 多租户支持：通过 `tenant_id` 隔离数据
- 知识库隔离：每个知识库独立集合/索引
- 权限控制：复用 Dify 现有 RBAC 体系

### 7.2 配置安全
- 敏感配置（密码、API Key）使用环境变量或密钥管理服务
- 配置文件支持加密存储
- 配置变更审计日志

---

## 8. 性能优化

### 8.1 缓存策略
- 查询结果缓存：Redis 缓存热门查询
- Embedding 缓存：避免重复计算
- 元数据缓存：减少数据库查询

### 8.2 批量处理
- 批量索引：减少 I/O 次数
- 批量检索：提高吞吐量
- 异步处理：非阻塞索引构建

### 8.3 连接池
- 数据库连接池：复用连接
- ES 连接池：HTTP Keep-Alive
- 线程池：并行检索

---

## 9. 测试策略

### 9.1 单元测试
- 各 DataStore 适配器独立测试
- 融合策略算法测试
- 配置服务逻辑测试

### 9.2 集成测试
- 端到端检索流程测试
- 三种资源级别切换测试
- Dify 兼容性测试

### 9.3 性能测试
- 基准测试：不同数据量下的性能
- 压力测试：并发查询性能
- 稳定性测试：长时间运行稳定性

---

## 10. 附录

### 10.1 环境变量清单

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATA_STORE_TYPE | 数据存储类型 | pgvector |
| SQLITE_DB_PATH | SQLite 数据库路径 | data/rag.db |
| PGVECTOR_HOST | PostgreSQL 主机 | localhost |
| PGVECTOR_PORT | PostgreSQL 端口 | 5432 |
| ELASTICSEARCH_HOSTS | ES 节点地址 | http://localhost:9200 |
| RESOURCE_LEVEL | 默认资源级别 | medium |

### 10.2 迁移指南

1. **从现有 Dify 迁移**
   - 备份现有数据
   - 安装新版本
   - 运行迁移脚本
   - 验证数据完整性

2. **资源级别切换**
   - 导出现有知识库配置
   - 修改资源级别
   - 重建索引
   - 验证检索效果
