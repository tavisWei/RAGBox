from __future__ import annotations


class BaseServiceError(ValueError):
    def __init__(self, description: str | None = None):
        self.description = description
        super().__init__(description)
