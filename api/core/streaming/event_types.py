"""SSE event types and data structures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """Server-Sent Event types."""

    MESSAGE = "message"
    ERROR = "error"
    DONE = "done"
    PING = "ping"
    TOKEN = "token"


@dataclass
class SSEEvent:
    """Server-Sent Event data structure.

    Follows the SSE specification:
    - id: Optional event identifier for reconnection
    - event: Event type (defaults to 'message')
    - retry: Reconnection time in milliseconds
    - data: Event payload
    """

    event: EventType = EventType.MESSAGE
    data: str = ""
    id: Optional[str] = None
    retry: Optional[int] = None

    def encode(self) -> str:
        """Encode as SSE wire format.

        Returns:
            SSE-formatted string ending with double newline.
        """
        lines: list[str] = []
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.event != EventType.MESSAGE:
            lines.append(f"event: {self.event.value}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        # Multiline data: each line prefixed with "data: "
        for line in self.data.split("\n"):
            lines.append(f"data: {line}")
        return "\n".join(lines) + "\n\n"
