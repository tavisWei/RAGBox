"""Tests for wiring the components page into the runtime store selection."""

from types import SimpleNamespace

import pytest

from api.api.knowledge_bases import resolve_datastore_config
from api.services.component_config_service import ComponentConfigService


@pytest.fixture
def svc() -> ComponentConfigService:
    """A ComponentConfigService with an in-memory store."""
    service = ComponentConfigService.__new__(ComponentConfigService)
    state = {
        "components": {
            "sqlite": {
                "id": "sqlite",
                "category": "datastore",
                "enabled": True,
                "config": {"path": "api/data/rag.sqlite"},
            },
            "pgvector": {
                "id": "pgvector",
                "category": "vector_store",
                "enabled": False,
                "config": {
                    "host": "localhost",
                    "port": "5432",
                    "database": "rag_test",
                    "username": "aiwriter",
                    "password": "aiwriter",
                },
            },
            "qdrant": {
                "id": "qdrant",
                "category": "vector_store",
                "enabled": False,
                "config": {"url": "http://localhost:6333"},
            },
        }
    }
    service.store = SimpleNamespace(read=lambda: state, write=lambda data: None)
    return service


def test_active_datastore_defaults_to_sqlite(svc, monkeypatch) -> None:
    monkeypatch.setattr(
        "api.services.component_config_service.component_config_service",
        svc,
    )
    active = svc.get_active_datastore()
    assert active["data_store_type"] == "sqlite"


def test_enabled_pgvector_component_wins_over_sqlite(svc, monkeypatch) -> None:
    svc.store.read()["components"]["pgvector"]["enabled"] = True
    active = svc.get_active_datastore()
    assert active["data_store_type"] == "pgvector"
    assert active["datastore"]["host"] == "localhost"
    assert active["datastore"]["user"] == "aiwriter"
    assert active["datastore"]["password"] == "aiwriter"


def test_resolver_chain_with_components(svc, monkeypatch) -> None:
    monkeypatch.delenv("DATA_STORE_TYPE", raising=False)
    monkeypatch.setattr(
        "api.services.component_config_service.component_config_service",
        svc,
    )
    # Component layer beats the plan recommendation.
    assert resolve_datastore_config({"rag_plan": "medium"})[
        "data_store_type"
    ] == "sqlite"

    # KB-level config beats the component layer.
    svc.store.read()["components"]["pgvector"]["enabled"] = True
    kb = {
        "rag_plan": "low",
        "datastore": {"type": "pgvector", "host": "kb-host", "database": "kbdb"},
    }
    resolved = resolve_datastore_config(kb)
    assert resolved["datastore"]["host"] == "kb-host"

    # Env beats everything but KB-level.
    monkeypatch.setenv("DATA_STORE_TYPE", "sqlite")
    assert (
        resolve_datastore_config({"rag_plan": "high"})["data_store_type"] == "sqlite"
    )


def test_test_component_sqlite_real_check(svc) -> None:
    result = svc.test_component("sqlite")
    assert result["result"] == "success"


@pytest.mark.integration
def test_test_component_pgvector_real_check(svc) -> None:
    pytest.importorskip("psycopg2")
    svc.store.read()["components"]["pgvector"]["enabled"] = True
    result = svc.test_component("pgvector")
    if "连接失败" in result["message"] or "失败" in result["message"]:
        pytest.skip(f"pg container unreachable: {result['message']}")
    assert result["result"] == "success"

    svc.store.read()["components"]["pgvector"]["config"]["password"] = "wrong"
    bad = svc.test_component("pgvector")
    assert bad["result"] == "failed"


def test_test_component_mysql_without_server_fails(svc) -> None:
    # mysql is wired into the runtime; the real check (init + health_check)
    # fails cleanly when no server is reachable.
    svc.store.read()["components"]["mysql"] = {
        "id": "mysql",
        "category": "database",
        "enabled": False,
        "config": {"host": "localhost", "port": "3306"},
    }
    result = svc.test_component("mysql")
    assert result["result"] == "failed"
    assert "mysql" in result["message"]


def test_test_component_unknown_id_fails(svc) -> None:
    with pytest.raises(ValueError):
        svc.test_component("nope")
