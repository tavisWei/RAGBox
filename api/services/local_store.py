from __future__ import annotations

from threading import Lock
from typing import Any, Callable, Dict

from api.services.business_store import manager


class LocalStore:
    """Whole-namespace dict store.

    Despite the name this is now a thin shell: every operation is delegated
    to the active business-store backend (local JSON files by default,
    MySQL when switched). The constructor argument keeps the historical
    "<namespace>.json" form.
    """

    _lock = Lock()

    def __init__(self, filename: str) -> None:
        self.namespace = filename[: -len(".json")] if filename.endswith(".json") else filename
        # Preserve the historical side effect: the namespace exists after init.
        backend = manager.get_backend()
        if backend.read_namespace(self.namespace) == {}:
            backend.write_namespace(self.namespace, {})

    def read(self) -> Dict[str, Any]:
        with self._lock:
            return manager.get_backend().read_namespace(self.namespace)

    def write(self, data: Dict[str, Any]) -> None:
        with self._lock:
            manager.get_backend().write_namespace(self.namespace, data)

    def update(
        self, updater: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> Dict[str, Any]:
        with self._lock:
            current = manager.get_backend().read_namespace(self.namespace)
            updated = updater(current)
            manager.get_backend().write_namespace(self.namespace, updated)
            return updated
