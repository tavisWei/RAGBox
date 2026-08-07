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
            # Migration: qdrant/milvus gained real store implementations,
            # mysql became a usable retrieval backend.
            changed = False
            for cid, name in (("qdrant", "Qdrant 专用向量库"), ("milvus", "Milvus 企业级向量库")):
                record = data["components"].get(cid)
                if record and "规划中" in str(record.get("config", {}).get("status", "")):
                    record["name"] = name
                    record["config"].pop("status", None)
                    changed = True
            mysql_record = data["components"].get("mysql")
            if mysql_record and "不作为" in str(
                mysql_record.get("config", {}).get("role", "")
            ):
                mysql_record["name"] = "MySQL 数据库"
                mysql_record["config"]["role"] = (
                    "可作为检索后端（BLOB 向量 + ngram 全文），向量检索为暴力余弦，适合中小规模"
                )
                changed = True
            if changed:
                self.store.write(data)
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
                "name": "MySQL 数据库",
                "category": "database",
                "enabled": False,
                "config": {
                    "host": os.getenv("MYSQL_HOST", "localhost"),
                    "port": os.getenv("MYSQL_PORT", "3306"),
                    "database": os.getenv("MYSQL_DATABASE", "rag_platform"),
                    "username": os.getenv("MYSQL_USER", "root"),
                    "password": os.getenv("MYSQL_PASSWORD", ""),
                    "role": "可作为检索后端（BLOB 向量 + ngram 全文），向量检索为暴力余弦，适合中小规模",
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
                "name": "Qdrant 专用向量库",
                "category": "vector_store",
                "enabled": False,
                "config": {
                    "url": os.getenv("QDRANT_URL", "http://localhost:6333"),
                    "api_key": os.getenv("QDRANT_API_KEY", ""),
                },
                "env_keys": ["QDRANT_URL", "QDRANT_API_KEY"],
                "updated_at": datetime.utcnow().isoformat(),
            },
            "milvus": {
                "id": "milvus",
                "name": "Milvus 企业级向量库",
                "category": "vector_store",
                "enabled": False,
                "config": {
                    "host": os.getenv("MILVUS_HOST", "localhost"),
                    "port": os.getenv("MILVUS_PORT", "19530"),
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
                "启用（enabled）的数据存储组件会作为全局默认检索后端注入运行时；"
                "知识库级配置与环境变量 DATA_STORE_TYPE 优先级更高。"
            )
            item["config"] = self._mask_config(item.get("config", {}))
            components.append(item)
        return {"data": components, "runtime_data_store": current_store}

    # Component ids that can act as the retrieval datastore.
    DATASTORE_COMPONENT_IDS = (
        "sqlite",
        "pgvector",
        "elasticsearch",
        "qdrant",
        "milvus",
        "mysql",
    )

    @staticmethod
    def _component_to_store_config(component: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a component record to (store_type, store kwargs)."""
        cid = component.get("id")
        config = component.get("config", {})
        if cid == "sqlite":
            return {
                "data_store_type": "sqlite",
                "datastore": {
                    "db_path": config.get("path") or "api/data/rag.sqlite"
                },
            }
        if cid == "pgvector":
            fields: Dict[str, Any] = {}
            if config.get("host"):
                fields["host"] = config["host"]
            if config.get("port"):
                fields["port"] = int(config["port"])
            if config.get("database"):
                fields["database"] = config["database"]
            if config.get("username"):
                fields["user"] = config["username"]
            if config.get("password"):
                fields["password"] = config["password"]
            result: Dict[str, Any] = {"data_store_type": "pgvector"}
            if fields:
                result["datastore"] = fields
            return result
        if cid == "elasticsearch":
            es_config: Dict[str, Any] = {}
            if config.get("hosts"):
                es_config["hosts"] = [
                    h.strip() for h in str(config["hosts"]).split(",") if h.strip()
                ]
            if config.get("username"):
                es_config["username"] = config["username"]
            if config.get("password"):
                es_config["password"] = config["password"]
            result = {"data_store_type": "elasticsearch"}
            if es_config:
                result["datastore"] = es_config
            return result
        if cid == "qdrant":
            qdrant_config: Dict[str, Any] = {}
            if config.get("url"):
                qdrant_config["url"] = config["url"]
            if config.get("api_key"):
                qdrant_config["api_key"] = config["api_key"]
            result = {"data_store_type": "qdrant"}
            if qdrant_config:
                result["datastore"] = qdrant_config
            return result
        if cid == "milvus":
            milvus_config: Dict[str, Any] = {}
            if config.get("host"):
                milvus_config["host"] = config["host"]
            if config.get("port"):
                milvus_config["port"] = int(config["port"])
            result = {"data_store_type": "milvus"}
            if milvus_config:
                result["datastore"] = milvus_config
            return result
        if cid == "mysql":
            mysql_config: Dict[str, Any] = {}
            if config.get("host"):
                mysql_config["host"] = config["host"]
            if config.get("port"):
                mysql_config["port"] = int(config["port"])
            if config.get("database"):
                mysql_config["database"] = config["database"]
            if config.get("username"):
                mysql_config["user"] = config["username"]
            if config.get("password"):
                mysql_config["password"] = config["password"]
            result = {"data_store_type": "mysql"}
            if mysql_config:
                result["datastore"] = mysql_config
            return result
        return None

    def get_active_datastore(self) -> Optional[Dict[str, Any]]:
        """Return the global datastore selection from the components page.

        An enabled datastore component is the deployment-wide default. When
        several are enabled, a non-SQLite backend wins over SQLite. Returns
        None when no datastore component is enabled.
        """
        data = self.store.read()
        enabled = [
            component
            for component in data.get("components", {}).values()
            if component.get("id") in self.DATASTORE_COMPONENT_IDS
            and component.get("enabled")
        ]
        if not enabled:
            return None
        non_sqlite = [c for c in enabled if c.get("id") != "sqlite"]
        chosen = non_sqlite[0] if non_sqlite else enabled[0]
        return self._component_to_store_config(chosen)

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
        if component_id in self.DATASTORE_COMPONENT_IDS:
            return self._test_datastore(record)
        return {"result": "failed", "message": "Unknown component"}

    def _test_datastore(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Real connectivity check: build the store and run health_check."""
        from api.core.rag.datasource.unified.data_store_factory import (
            DataStoreFactory,
        )

        mapped = self._component_to_store_config(record) or {}
        store_type = mapped.get("data_store_type", record.get("id"))
        try:
            store = DataStoreFactory.create(
                store_type=store_type, config=mapped.get("datastore") or {}
            )
            ok = store.health_check()
        except Exception as exc:
            return {
                "result": "failed",
                "message": f"{record.get('id')} 初始化/健康检查失败: {exc}",
            }
        if not ok:
            return {
                "result": "failed",
                "message": f"{record.get('id')} 健康检查未通过",
            }
        return {
            "result": "success",
            "message": f"{record.get('id')} 初始化与健康检查通过",
        }

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
