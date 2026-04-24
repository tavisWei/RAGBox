from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict


class LocalStore:
    _lock = Lock()

    def __init__(self, filename: str) -> None:
        base_dir = Path(__file__).resolve().parent.parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = base_dir / filename
        if not self.file_path.exists():
            self._write({})

    def read(self) -> Dict[str, Any]:
        with self._lock:
            if not self.file_path.exists():
                return {}
            return json.loads(self.file_path.read_text(encoding="utf-8"))

    def write(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._write(data)

    def update(
        self, updater: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> Dict[str, Any]:
        with self._lock:
            current = self.read()
            updated = updater(current)
            self._write(updated)
            return updated

    def _write(self, data: Dict[str, Any]) -> None:
        self.file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
