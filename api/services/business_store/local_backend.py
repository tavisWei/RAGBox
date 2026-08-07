"""Local JSON-file business store backend (the historical default)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .base import BusinessStoreBackend

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Bootstrap-level files that must never be treated as business namespaces.
EXCLUDED_FILES = {"system_settings.json"}


class LocalBackend(BusinessStoreBackend):
    def backend_type(self) -> str:
        return "local"

    @staticmethod
    def _path(namespace: str) -> Path:
        return DATA_DIR / f"{namespace}.json"

    def read_namespace(self, namespace: str) -> Dict[str, Any]:
        path = self._path(namespace)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_namespace(self, namespace: str, data: Dict[str, Any]) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._path(namespace).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list_namespaces(self) -> List[str]:
        if not DATA_DIR.exists():
            return []
        return sorted(
            path.stem
            for path in DATA_DIR.glob("*.json")
            if path.name not in EXCLUDED_FILES
        )

    def health_check(self) -> bool:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False
