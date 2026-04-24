"""SSE encoder for streaming responses."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Optional

from .event_types import EventType, SSEEvent


class SSEEncoder:
    """Server-Sent Events encoder for streaming responses.

    SSE wire format per event:
        id: <event_id>
        event: <event_type>
        data: <json_data>

    Events are separated by a blank line (double newline).

    Usage:
        encoder = SSEEncoder()
        chunk = encoder.encode_token("hello")
    """

    def __init__(self) -> None:
        self._event_id: int = 0

    @property
    def event_id(self) -> int:
        """Current event ID counter."""
        return self._event_id

    def encode_message(
        self,
        data: Any,
        event: EventType = EventType.MESSAGE,
    ) -> str:
        """Encode a message as an SSE event.

        Args:
            data: Payload to encode. Dicts are JSON-serialized.
            event: SSE event type.

        Returns:
            SSE-formatted string.
        """
        self._event_id += 1
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False)
        sse_event = SSEEvent(
            id=str(self._event_id),
            event=event,
            data=str(data),
        )
        return sse_event.encode()

    def encode_token(self, token: str) -> str:
        """Encode a single token for streaming output.

        Args:
            token: Text token from LLM stream.

        Returns:
            SSE-formatted token event.
        """
        return self.encode_message({"token": token}, EventType.TOKEN)

    def encode_error(self, error: str) -> str:
        """Encode an error event.

        Args:
            error: Error message.

        Returns:
            SSE-formatted error event.
        """
        return self.encode_message({"error": error}, EventType.ERROR)

    def encode_done(self) -> str:
        """Encode a stream-completion signal.

        Returns:
            SSE-formatted done event.
        """
        return self.encode_message({}, EventType.DONE)

    def encode_ping(self) -> str:
        """Encode a keepalive ping.

        Returns:
            SSE-formatted ping event (no event ID increment).
        """
        return SSEEvent(event=EventType.PING).encode()

    async def stream_generator(
        self,
        token_generator: AsyncGenerator[str, None],
        timeout_seconds: float = 60.0,
    ) -> AsyncGenerator[str, None]:
        """Wrap an async token generator with SSE encoding and timeout.

        Args:
            token_generator: Async generator yielding text tokens.
            timeout_seconds: Max seconds to wait for the next token.

        Yields:
            SSE-formatted strings for each token, followed by a done event.
        """
        try:
            while True:
                try:
                    token = await asyncio.wait_for(
                        token_generator.__anext__(),
                        timeout=timeout_seconds,
                    )
                    yield self.encode_token(token)
                except StopAsyncIteration:
                    yield self.encode_done()
                    break
                except asyncio.TimeoutError:
                    yield self.encode_error("Stream timeout")
                    break
        except Exception as exc:
            yield self.encode_error(str(exc))
