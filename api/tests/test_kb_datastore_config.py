"""Tests for KB-level datastore configuration and the unified resolver."""

import os
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from api.api.knowledge_bases import _mask_dsn, resolve_datastore_config
from api.main import app

client = TestClient(app)


def auth_headers() -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


DSN = "postgresql://aiwriter:aiwriter@localhost:5432/aiwriter"


def test_resolver_explicit_kb_config_wins(monkeypatch) -> None:
    monkeypatch.setenv("DATA_STORE_TYPE", "elasticsearch")
    kb = {"rag_plan": "low", "datastore": {"type": "pgvector", "dsn": DSN}}
    config = resolve_datastore_config(kb)
    assert config["data_store_type"] == "pgvector"
    assert config["datastore"]["host"] == "localhost"
    assert config["datastore"]["database"] == "aiwriter"


def test_resolver_env_beats_plan(monkeypatch) -> None:
    monkeypatch.setenv("DATA_STORE_TYPE", "sqlite")
    kb = {"rag_plan": "medium"}  # medium recommends pgvector
    assert resolve_datastore_config(kb)["data_store_type"] == "sqlite"


def test_resolver_plan_fallback_and_empty_kb(monkeypatch) -> None:
    monkeypatch.delenv("DATA_STORE_TYPE", raising=False)
    # Isolate from the components page default (sqlite enabled).
    from api.services.component_config_service import component_config_service

    monkeypatch.setattr(
        component_config_service, "get_active_datastore", lambda: None
    )
    assert (
        resolve_datastore_config({"rag_plan": "medium"})["data_store_type"]
        == "pgvector"
    )
    # No KB context must never default to an external backend.
    assert resolve_datastore_config({})["data_store_type"] == "sqlite"


def test_mask_dsn() -> None:
    assert _mask_dsn(DSN) == "postgresql://aiwriter:****@localhost:5432/aiwriter"
    assert _mask_dsn("postgresql://localhost/db") == "postgresql://localhost/db"


def test_update_endpoint_stores_masks_and_preserves_dsn() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/knowledge-bases", json={"name": "ds-cfg-test"}, headers=headers
    )
    kb_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"datastore": {"type": "pgvector", "dsn": DSN}},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["datastore"]["dsn"] == "postgresql://aiwriter:****@localhost:5432/aiwriter"

    # Saving again with the masked DSN omitted must not clobber the real one:
    # the resolver has to see the original password.
    updated2 = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"datastore": {"type": "pgvector"}},
        headers=headers,
    )
    assert updated2.status_code == 200
    from api.api import knowledge_bases as kb_module

    assert kb_module._knowledge_bases[kb_id]["datastore"]["dsn"] == DSN

    # Clearing the override falls back to plan/env resolution.
    cleared = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"datastore": {"type": ""}},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert "datastore" not in kb_module._knowledge_bases[kb_id]

    client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)


def test_field_based_pgvector_config_and_password_preservation() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/knowledge-bases", json={"name": "ds-fields-test"}, headers=headers
    )
    kb_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={
            "datastore": {
                "type": "pgvector",
                "host": "localhost",
                "port": 5432,
                "user": "aiwriter",
                "password": "aiwriter",
                "database": "rag_test",
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200
    datastore = updated.json()["datastore"]
    assert datastore["password"] == "****"
    assert datastore["host"] == "localhost"
    assert datastore["database"] == "rag_test"

    # Resolver turns the field-based config into store kwargs.
    from api.api import knowledge_bases as kb_module

    config = resolve_datastore_config(kb_module._knowledge_bases[kb_id])
    assert config["datastore"] == {
        "host": "localhost",
        "port": 5432,
        "user": "aiwriter",
        "password": "aiwriter",
        "database": "rag_test",
    }

    # Saving without the password keeps the stored one.
    client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"datastore": {"type": "pgvector", "host": "localhost", "port": 5432, "user": "aiwriter", "database": "rag_test"}},
        headers=headers,
    )
    config2 = resolve_datastore_config(kb_module._knowledge_bases[kb_id])
    assert config2["datastore"]["password"] == "aiwriter"

    client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)


def test_update_endpoint_rejects_unknown_datastore_type() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/knowledge-bases", json={"name": "ds-bad-test"}, headers=headers
    )
    kb_id = created.json()["id"]
    response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"datastore": {"type": "mysql"}},
        headers=headers,
    )
    assert response.status_code == 400
    client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)


def _container_available() -> bool:
    try:
        import psycopg2

        parsed = urlparse(DSN)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname=parsed.path.lstrip("/"),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _container_available(), reason="pg container unreachable")
def test_test_datastore_endpoint_ok_and_bad() -> None:
    headers = auth_headers()
    ok = client.post(
        "/api/v1/knowledge-bases/test-datastore",
        json={"type": "pgvector", "dsn": DSN},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"

    bad = client.post(
        "/api/v1/knowledge-bases/test-datastore",
        json={
            "type": "pgvector",
            "dsn": "postgresql://aiwriter:wrong@localhost:5432/aiwriter",
        },
        headers=headers,
    )
    assert bad.status_code == 400
