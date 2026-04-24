from typing import Any, Dict

from api.services.local_store import LocalStore


class KnowledgeBaseStore:
    def __init__(self) -> None:
        self.store = LocalStore("knowledge_bases.json")
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        data = self.store.read()
        if not data:
            self.store.write({"knowledge_bases": {}, "documents": {}})

    def read_all(self) -> Dict[str, Any]:
        return self.store.read()

    def write_all(self, data: Dict[str, Any]) -> None:
        self.store.write(data)


knowledge_base_store = KnowledgeBaseStore()
