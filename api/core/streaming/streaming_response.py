"""FastAPI streaming response wrapper for SSE."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

from .sse_encoder import SSEEncoder


class SSEStreamingResponse(StreamingResponse):
    """FastAPI StreamingResponse pre-configured for SSE.

    Sets the correct media type and headers for Server-Sent Events,
    and provides helpers for client disconnect detection.
    """

    media_type = "text/event-stream"

    def __init__(
        self,
        content: Any,
        headers: Optional[dict[str, str]] = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        """Initialize SSE streaming response.

        Args:
            content: Async iterable yielding SSE-formatted strings.
            headers: Optional extra HTTP headers.
            timeout_seconds: Default timeout for downstream generators.
        """
        default_headers: dict[str, str] = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
        if headers:
            default_headers.update(headers)

        super().__init__(
            content=content,
            media_type=self.media_type,
            headers=default_headers,
        )
        self.timeout_seconds = timeout_seconds

    @staticmethod
    async def is_client_disconnected(request: Request) -> bool:
        """Check whether the client has disconnected.

        Args:
            request: The incoming FastAPI request.

        Returns:
            True if the client is disconnected.
        """
        return await request.is_disconnected()

    @classmethod
    def from_token_generator(
        cls,
        token_generator: AsyncGenerator[str, None],
        *,
        request: Optional[Request] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_seconds: float = 60.0,
    ) -> SSEStreamingResponse:
        """Create an SSE response directly from a token generator.

        Args:
            token_generator: Async generator yielding raw text tokens.
            request: Optional request reference for disconnect detection.
            headers: Extra HTTP headers.
            timeout_seconds: Per-token timeout.

        Returns:
            Configured SSEStreamingResponse.
        """
        encoder = SSEEncoder()
        sse_stream = encoder.stream_generator(
            token_generator,
            timeout_seconds=timeout_seconds,
        )

        # Optionally wrap to stop early on client disconnect
        if request is not None:

            async def _guarded() -> AsyncGenerator[str, None]:
                async for chunk in sse_stream:
                    if await request.is_disconnected():
                        return
                    yield chunk

            return cls(
                content=_guarded(), headers=headers, timeout_seconds=timeout_seconds
            )

        return cls(content=sse_stream, headers=headers, timeout_seconds=timeout_seconds)
