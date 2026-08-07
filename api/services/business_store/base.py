"""Business-data storage abstraction.

A "namespace" maps 1:1 to a LocalStore JSON file (users, sessions, apps, ...).
Backends keep the same whole-namespace dict semantics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BusinessStoreBackend(ABC):
    @abstractmethod
    def backend_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_namespace(self, namespace: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def write_namespace(self, namespace: str, data: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_namespaces(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError
