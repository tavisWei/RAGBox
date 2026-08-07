"""Active business-store backend resolution, switching and migration.

Precedence: system settings file > BUSINESS_STORE_TYPE env > local files.
The settings file is read/written directly (never through LocalStore) to
avoid a bootstrap cycle.
"""

from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any, Dict, List, Optional

from .base import BusinessStoreBackend
from .local_backend import DATA_DIR, LocalBackend
from .mysql_backend import MySQLBackend

_SETTINGS_PATH = DATA_DIR / "system_settings.json"

_lock = Lock()
_cached: Optional[BusinessStoreBackend] = None


def _read_settings() -> Dict[str, Any]:
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_settings(settings: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def make_backend(
    backend_type: str, config: Optional[Dict[str, Any]] = None
) -> BusinessStoreBackend:
    if backend_type == "local":
        return LocalBackend()
    if backend_type == "mysql":
        return MySQLBackend(config or {})
    raise ValueError(f"Unknown business store type: {backend_type}")


def current_selection() -> Dict[str, Any]:
    settings = _read_settings().get("business_store") or {}
    if settings.get("type"):
        return settings
    env_type = os.getenv("BUSINESS_STORE_TYPE")
    if env_type:
        return {"type": env_type}
    return {"type": "local"}


def get_backend() -> BusinessStoreBackend:
    global _cached
    with _lock:
        if _cached is None:
            selection = current_selection()
            _cached = make_backend(
                selection.get("type", "local"), selection.get("config")
            )
        return _cached


def switch_backend(
    backend_type: str, config: Optional[Dict[str, Any]] = None
) -> BusinessStoreBackend:
    """Persist the selection and swap the active backend."""
    global _cached
    backend = make_backend(backend_type, config)
    settings = _read_settings()
    settings["business_store"] = {"type": backend_type, "config": config or {}}
    _write_settings(settings)
    with _lock:
        _cached = backend
    return backend


def migrate_and_switch(
    target_type: str, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Copy every namespace to the target backend, verify, then switch.

    Any failure aborts before the switch, leaving the current backend active.
    """
    source = get_backend()
    target = make_backend(target_type, config)
    if not target.health_check():
        raise RuntimeError(f"Target backend '{target_type}' is not reachable")

    namespaces = source.list_namespaces()
    copied: List[str] = []
    for namespace in namespaces:
        payload = source.read_namespace(namespace)
        target.write_namespace(namespace, payload)
        if target.read_namespace(namespace) != payload:
            raise RuntimeError(
                f"Verification failed for namespace '{namespace}'; not switching"
            )
        copied.append(namespace)

    switch_backend(target_type, config)
    return {
        "switched": True,
        "from": source.backend_type(),
        "to": target_type,
        "namespaces": copied,
    }
