from __future__ import annotations

import os
import socket
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from .local_store import LocalStore


class ComponentConfigService:
    def __init__(self) -> None:
        self.store = LocalStore("component_configs.json")
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        data = self.store.read()
        if data.get("components"):
            return
        data["components"] = {
            "sqlite": {
                "id": "sqlite",
                "name": "SQLite 轻量 RAG 存储",
                "category": "datastore",
                "enabled": True,
                "config": {"path": os.getenv("SQLITE_DB_PATH", "api/data/rag.sqlite")},
                "env_keys": ["DATA_STORE_TYPE", "SQLITE_DB_PATH"],
                "updated_at": datetime.utcnow().isoformat(),
            },
            "mysql": {
                "id": "mysql",
                "name": "MySQL 业务数据库",
                "category": "database",
                "enabled": False,
                "config": {
                    "host": os.getenv("MYSQL_HOST", "localhost"),
                    "port": os.getenv("MYSQL_PORT", "3306"),
                    "database": os.getenv("MYSQL_DATABASE", "rag_platform"),
                    "username": os.getenv("MYSQL_USER", "root"),
                    "password": os.getenv("MYSQL_PASSWORD", ""),
                    "role": "业务数据/用户/应用配置，不作为知识库向量检索后端",
                },
                "env_keys": [
                    "DATABASE_URL",
                    "MYSQL_HOST",
                    "MYSQL_PORT",
                    "MYSQL_DATABASE",
                    "MYSQL_USER",
                    "MYSQL_PASSWORD",
                ],
                "updated_at": datetime.utcnow().isoformat(),
            },
            "pgvector": {
                "id": "pgvector",
                "name": "PostgreSQL / pgvector",
                "category": "vector_store",
                "enabled": False,
                "config": {
                    "host": os.getenv("PGVECTOR_HOST", "localhost"),
                    "port": os.getenv("PGVECTOR_PORT", "5432"),
                    "database": os.getenv("PGVECTOR_DATABASE", "rag_platform"),
                    "username": os.getenv("PGVECTOR_USER", "postgres"),
                    "password": os.getenv("PGVECTOR_PASSWORD", ""),
                },
                "env_keys": [
                    "DATA_STORE_TYPE",
                    "PGVECTOR_HOST",
                    "PGVECTOR_PORT",
                    "PGVECTOR_DATABASE",
                    "PGVECTOR_USER",
                    "PGVECTOR_PASSWORD",
                ],
                "updated_at": datetime.utcnow().isoformat(),
            },
            "elasticsearch": {
                "id": "elasticsearch",
                "name": "Elasticsearch",
                "category": "search_engine",
                "enabled": False,
                "config": {
                    "hosts": os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200"),
                    "username": os.getenv("ELASTICSEARCH_USERNAME", ""),
                    "password": os.getenv("ELASTICSEARCH_PASSWORD", ""),
                },
                "env_keys": [
                    "DATA_STORE_TYPE",
                    "ELASTICSEARCH_HOSTS",
                    "ELASTICSEARCH_USERNAME",
                    "ELASTICSEARCH_PASSWORD",
                ],
                "updated_at": datetime.utcnow().isoformat(),
            },
            "qdrant": {
                "id": "qdrant",
                "name": "Qdrant 专用向量库（规划）",
                "category": "vector_store",
                "enabled": False,
                "config": {
                    "url": os.getenv("QDRANT_URL", "http://localhost:6333"),
                    "api_key": os.getenv("QDRANT_API_KEY", ""),
                    "status": "规划中：推荐作为企业增强后的专用向量库升级路径",
                },
                "env_keys": ["QDRANT_URL", "QDRANT_API_KEY"],
                "updated_at": datetime.utcnow().isoformat(),
            },
            "milvus": {
                "id": "milvus",
                "name": "Milvus 企业级向量库（规划）",
                "category": "vector_store",
                "enabled": False,
                "config": {
                    "host": os.getenv("MILVUS_HOST", "localhost"),
                    "port": os.getenv("MILVUS_PORT", "19530"),
                    "status": "规划中：适合超大规模/多租户/分布式企业部署",
                },
                "env_keys": ["MILVUS_HOST", "MILVUS_PORT"],
                "updated_at": datetime.utcnow().isoformat(),
            },
        }
        self.store.write(data)

    def list_components(self) -> Dict[str, Any]:
        data = self.store.read()
        current_store = os.getenv("DATA_STORE_TYPE", "sqlite")
        components = []
        for component in data.get("components", {}).values():
            item = dict(component)
            item["active"] = item["id"] == current_store
            item["runtime_note"] = (
                "当前运行时读取环境变量；这里保存连接参数供管理员记录和连通性检查，不会热切换运行中存储。"
            )
            item["config"] = self._mask_config(item.get("config", {}))
            components.append(item)
        return {"data": components, "runtime_data_store": current_store}

    def update_component(
        self, component_id: str, config: Dict[str, Any], enabled: bool
    ) -> Dict[str, Any]:
        data = self.store.read()
        components = data.get("components", {})
        if component_id not in components:
            raise ValueError("Component not found")
        record = components[component_id]
        existing = record.get("config", {})
        for key, value in config.items():
            if key == "password" and value == "********":
                continue
            existing[key] = value
        record["config"] = existing
        record["enabled"] = enabled
        record["updated_at"] = datetime.utcnow().isoformat()
        self.store.write(data)
        public = dict(record)
        public["config"] = self._mask_config(public.get("config", {}))
        return public

    def test_component(self, component_id: str) -> Dict[str, Any]:
        data = self.store.read()
        record = data.get("components", {}).get(component_id)
        if not record:
            raise ValueError("Component not found")
        config = record.get("config", {})
        if component_id == "sqlite":
            return {
                "result": "success",
                "message": "SQLite 使用本地文件，无需网络连接。",
            }
        if component_id in {"pgvector", "mysql", "milvus"}:
            return self._test_tcp(
                config.get("host", "localhost"),
                int(
                    config.get("port")
                    or (
                        5432
                        if component_id == "pgvector"
                        else 3306
                        if component_id == "mysql"
                        else 19530
                    )
                ),
                component_id,
            )
        if component_id == "elasticsearch":
            host, port = self._parse_http_host(
                config.get("hosts", "http://localhost:9200")
            )
            return self._test_tcp(host, port, "elasticsearch")
        if component_id == "qdrant":
            host, port = self._parse_http_host(
                config.get("url", "http://localhost:6333")
            )
            return self._test_tcp(host, port, "qdrant")
        return {"result": "failed", "message": "Unknown component"}

    def _test_tcp(self, host: str, port: int, label: str) -> Dict[str, Any]:
        test_id = str(uuid4())
        try:
            with socket.create_connection((host, port), timeout=2):
                return {
                    "result": "success",
                    "message": f"{label} TCP 连接成功",
                    "test_id": test_id,
                }
        except OSError as exc:
            return {
                "result": "failed",
                "message": f"{label} TCP 连接失败: {exc}",
                "test_id": test_id,
            }

    def _parse_http_host(self, value: str) -> tuple[str, int]:
        first = (
            value.split(",")[0].strip().replace("http://", "").replace("https://", "")
        )
        host, _, port = first.partition(":")
        return host or "localhost", int(port or 9200)

    def _mask_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        masked = dict(config)
        if masked.get("password"):
            masked["password"] = "********"
        if masked.get("api_key"):
            masked["api_key"] = "********"
        return masked


component_config_service = ComponentConfigService()
