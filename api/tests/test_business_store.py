"""Tests for the business store backends, manager resolution and migration."""

import json
import sys
import types
from typing import Any, Dict

import pytest

from api.services.business_store import manager
from api.services.business_store.local_backend import LocalBackend


# ---------------------------------------------------------------------------
# Fake pymysql with a shared in-memory business_kv table
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()).upper()
        table = self.conn.table
        if normalized.startswith("CREATE TABLE"):
            pass
        elif normalized.startswith("REPLACE INTO"):
            table[params[0]] = params[1]
        elif normalized.startswith("SELECT PAYLOAD"):
            self._rows = [(table[params[0]],)] if params[0] in table else []
        elif normalized.startswith("SELECT NAMESPACE"):
            self._rows = [(key,) for key in sorted(table)]
        elif normalized.startswith("SELECT 1"):
            self._rows = [(1,)]
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, table, **kwargs):
        self.table = table
        self.kwargs = kwargs

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_pymysql(monkeypatch):
    shared_table: Dict[str, str] = {}
    fake = types.ModuleType("pymysql")
    fake.connect = lambda **kwargs: _FakeConnection(shared_table, **kwargs)
    monkeypatch.setitem(sys.modules, "pymysql", fake)
    return shared_table


@pytest.fixture
def isolated_manager(monkeypatch, tmp_path):
    """Point the manager and local backend at a temp data dir."""
    import api.services.business_store.local_backend as local_module

    monkeypatch.setattr(local_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(manager, "_SETTINGS_PATH", tmp_path / "system_settings.json")
    monkeypatch.setattr(manager, "_cached", None)
    yield tmp_path
    monkeypatch.setattr(manager, "_cached", None)


def test_local_backend_roundtrip(isolated_manager) -> None:
    backend = LocalBackend()
    backend.write_namespace("users", {"users": {"u1": {"name": "Ada"}}})
    assert backend.read_namespace("users")["users"]["u1"]["name"] == "Ada"
    assert "users" in backend.list_namespaces()
    # The bootstrap settings file is never a business namespace.
    (isolated_manager / "system_settings.json").write_text("{}")
    assert "system_settings" not in backend.list_namespaces()


def test_mysql_backend_roundtrip(fake_pymysql) -> None:
    backend = manager.make_backend("mysql", {"host": "fake"})
    backend.write_namespace("apps", {"apps": {"a1": {"name": "demo"}}})
    assert backend.read_namespace("apps")["apps"]["a1"]["name"] == "demo"
    assert backend.read_namespace("missing") == {}
    assert backend.list_namespaces() == ["apps"]
    assert backend.health_check() is True


def test_manager_defaults_to_local(isolated_manager) -> None:
    assert manager.current_selection()["type"] == "local"
    assert manager.get_backend().backend_type() == "local"


def test_migrate_local_to_mysql_and_back(isolated_manager, fake_pymysql) -> None:
    source = manager.get_backend()
    source.write_namespace("users", {"users": {"u1": {}}})
    source.write_namespace("apps", {"apps": {}})

    result = manager.migrate_and_switch(
        "mysql", {"host": "fake", "database": "rag_platform"}
    )
    assert result["switched"] is True
    assert result["from"] == "local"
    assert set(result["namespaces"]) == {"apps", "users"}
    assert manager.get_backend().backend_type() == "mysql"
    # Data landed in the fake MySQL table.
    assert json.loads(fake_pymysql["users"])["users"]["u1"] == {}

    # Round-trip back to local works and keeps data.
    back = manager.migrate_and_switch("local")
    assert back["to"] == "local"
    assert manager.get_backend().read_namespace("users")["users"]["u1"] == {}


def test_migrate_failure_does_not_switch(isolated_manager, monkeypatch) -> None:
    manager.get_backend().write_namespace("users", {"users": {}})

    class BrokenBackend:
        def backend_type(self):
            return "mysql"

        def health_check(self):
            return True

        def write_namespace(self, ns, data):
            pass

        def read_namespace(self, ns):
            return {"corrupted": True}  # verification must fail

        def list_namespaces(self):
            return ["users"]

    monkeypatch.setattr(manager, "make_backend", lambda t, c=None: BrokenBackend())
    with pytest.raises(RuntimeError, match="Verification failed"):
        manager.migrate_and_switch("mysql", {})
    assert manager.current_selection()["type"] == "local"


def test_env_override(monkeypatch, isolated_manager) -> None:
    monkeypatch.setenv("BUSINESS_STORE_TYPE", "mysql")
    assert manager.current_selection()["type"] == "mysql"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_storage_status_endpoint() -> None:
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/system/storage", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["business_store"]["type"] in {"local", "mysql"}
    assert "users" in body["business_store"]["namespaces"]
    assert body["vector_options"]


def test_migrate_endpoint_rejects_same_backend() -> None:
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    current = client.get("/api/v1/system/storage", headers=headers).json()[
        "business_store"
    ]["type"]
    response = client.post(
        "/api/v1/system/storage/business/migrate",
        json={"type": current},
        headers=headers,
    )
    assert response.status_code == 400
