"""MySQL business store backend: one row per namespace in `business_kv`."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from .base import BusinessStoreBackend

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `business_kv` (
    namespace VARCHAR(128) PRIMARY KEY,
    payload MEDIUMTEXT,
    updated_at VARCHAR(40)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


class MySQLBackend(BusinessStoreBackend):
    def __init__(self, config: Dict[str, Any]):
        try:
            import pymysql  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "pymysql is required for the MySQL business store. "
                "Install it with: pip install pymysql"
            ) from exc
        self.config = config
        self._ensure_table()

    def backend_type(self) -> str:
        return "mysql"

    def _connect(self):
        import pymysql

        return pymysql.connect(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 3306)),
            user=self.config.get("user", "root"),
            password=self.config.get("password", ""),
            database=self.config.get("database", "rag_platform"),
            charset="utf8mb4",
        )

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    def read_namespace(self, namespace: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM `business_kv` WHERE namespace = %s",
                    (namespace,),
                )
                row = cur.fetchone()
            if not row or not row[0]:
                return {}
            return json.loads(row[0])
        finally:
            conn.close()

    def write_namespace(self, namespace: str, data: Dict[str, Any]) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "REPLACE INTO `business_kv` (namespace, payload, updated_at) "
                    "VALUES (%s, %s, %s)",
                    (
                        namespace,
                        json.dumps(data, ensure_ascii=False),
                        datetime.utcnow().isoformat(),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_namespaces(self) -> List[str]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT namespace FROM `business_kv` ORDER BY namespace")
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def health_check(self) -> bool:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                conn.close()
        except Exception:
            return False
