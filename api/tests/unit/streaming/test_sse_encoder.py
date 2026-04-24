"""Tests for SSE encoder and streaming infrastructure."""

import asyncio
import pytest

from api.core.streaming.event_types import EventType, SSEEvent
from api.core.streaming.sse_encoder import SSEEncoder
from api.core.streaming.streaming_response import SSEStreamingResponse


class TestSSEEvent:
    def test_encode_basic_message(self):
        event = SSEEvent(data="hello world")
        result = event.encode()
        assert result == "data: hello world\n\n"

    def test_encode_with_id(self):
        event = SSEEvent(id="123", data="test")
        result = event.encode()
        assert "id: 123" in result
        assert "data: test" in result

    def test_encode_with_event_type(self):
        event = SSEEvent(event=EventType.ERROR, data="error message")
        result = event.encode()
        assert "event: error" in result
        assert "data: error message" in result

    def test_encode_with_retry(self):
        event = SSEEvent(data="test", retry=5000)
        result = event.encode()
        assert "retry: 5000" in result

    def test_encode_all_fields(self):
        event = SSEEvent(
            id="42",
            event=EventType.TOKEN,
            data="token data",
            retry=3000,
        )
        result = event.encode()
        assert "id: 42" in result
        assert "event: token" in result
        assert "retry: 3000" in result
        assert "data: token data" in result

    def test_encode_multiline_data(self):
        event = SSEEvent(data="line1\nline2\nline3")
        result = event.encode()
        assert "data: line1" in result
        assert "data: line2" in result
        assert "data: line3" in result

    def test_message_event_omitted_from_output(self):
        event = SSEEvent(event=EventType.MESSAGE, data="test")
        result = event.encode()
        assert "event:" not in result

    def test_event_type_values(self):
        assert EventType.MESSAGE.value == "message"
        assert EventType.ERROR.value == "error"
        assert EventType.DONE.value == "done"
        assert EventType.PING.value == "ping"
        assert EventType.TOKEN.value == "token"


class TestSSEEncoder:
    def test_initialization(self):
        encoder = SSEEncoder()
        assert encoder.event_id == 0

    def test_encode_message_increments_id(self):
        encoder = SSEEncoder()
        result1 = encoder.encode_message("first")
        result2 = encoder.encode_message("second")
        assert encoder.event_id == 2
        assert "id: 1" in result1
        assert "id: 2" in result2

    def test_encode_message_with_dict(self):
        encoder = SSEEncoder()
        result = encoder.encode_message({"key": "value"})
        assert "data:" in result
        assert '"key": "value"' in result or '"key":"value"' in result

    def test_encode_token(self):
        encoder = SSEEncoder()
        result = encoder.encode_token("hello")
        assert "event: token" in result
        assert '"token": "hello"' in result or '"token":"hello"' in result

    def test_encode_error(self):
        encoder = SSEEncoder()
        result = encoder.encode_error("something went wrong")
        assert "event: error" in result
        assert "something went wrong" in result

    def test_encode_done(self):
        encoder = SSEEncoder()
        result = encoder.encode_done()
        assert "event: done" in result

    def test_encode_ping(self):
        encoder = SSEEncoder()
        result = encoder.encode_ping()
        assert "event: ping" in result
        assert "id:" not in result

    def test_ping_does_not_increment_id(self):
        encoder = SSEEncoder()
        encoder.encode_message("first")
        initial_id = encoder.event_id
        encoder.encode_ping()
        assert encoder.event_id == initial_id

    @pytest.mark.asyncio
    async def test_stream_generator_yields_tokens(self):
        encoder = SSEEncoder()

        async def token_gen():
            yield "hello"
            yield " world"

        results = []
        async for chunk in encoder.stream_generator(token_gen()):
            results.append(chunk)

        assert len(results) == 3
        assert "event: token" in results[0]
        assert "hello" in results[0]
        assert "event: token" in results[1]
        assert "world" in results[1]
        assert "event: done" in results[2]

    @pytest.mark.asyncio
    async def test_stream_generator_timeout(self):
        encoder = SSEEncoder()

        async def slow_gen():
            yield "first"
            await asyncio.sleep(2)
            yield "second"

        results = []
        async for chunk in encoder.stream_generator(slow_gen(), timeout_seconds=0.5):
            results.append(chunk)

        assert len(results) == 2
        assert "event: token" in results[0]
        assert "event: error" in results[1]
        assert "timeout" in results[1].lower()

    @pytest.mark.asyncio
    async def test_stream_generator_handles_exception(self):
        encoder = SSEEncoder()

        async def failing_gen():
            yield "first"
            raise ValueError("test error")

        results = []
        async for chunk in encoder.stream_generator(failing_gen()):
            results.append(chunk)

        assert len(results) == 2
        assert "event: token" in results[0]
        assert "event: error" in results[1]
        assert "test error" in results[1]


class TestSSEStreamingResponse:
    def test_media_type(self):
        assert SSEStreamingResponse.media_type == "text/event-stream"

    def test_default_headers(self):
        async def gen():
            yield "data: test\n\n"

        response = SSEStreamingResponse(content=gen())
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"

    def test_custom_headers_merge(self):
        async def gen():
            yield "data: test\n\n"

        response = SSEStreamingResponse(
            content=gen(),
            headers={"X-Custom": "value"},
        )
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-custom"] == "value"

    def test_timeout_seconds_attribute(self):
        async def gen():
            yield "data: test\n\n"

        response = SSEStreamingResponse(content=gen(), timeout_seconds=30.0)
        assert response.timeout_seconds == 30.0

    @pytest.mark.asyncio
    async def test_is_client_disconnected(self):
        from unittest.mock import MagicMock

        async def return_true():
            return True

        request = MagicMock()
        request.is_disconnected = return_true

        result = await SSEStreamingResponse.is_client_disconnected(request)
        assert result is True

    @pytest.mark.asyncio
    async def test_from_token_generator(self):
        async def tokens():
            yield "hello"
            yield "world"

        response = SSEStreamingResponse.from_token_generator(tokens())
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_from_token_generator_with_disconnect_detection(self):
        from unittest.mock import MagicMock

        async def tokens():
            yield "hello"
            yield "world"

        async def return_false():
            return False

        request = MagicMock()
        request.is_disconnected = return_false

        response = SSEStreamingResponse.from_token_generator(tokens(), request=request)
        assert response.media_type == "text/event-stream"
        assert response.timeout_seconds == 60.0

    @pytest.mark.asyncio
    async def test_from_token_generator_disconnect_stops_early(self):
        from unittest.mock import MagicMock

        call_count = [0]

        async def tokens():
            yield "first"
            yield "second"
            yield "third"

        async def disconnect_after_first():
            call_count[0] += 1
            return call_count[0] > 1

        request = MagicMock()
        request.is_disconnected = disconnect_after_first

        response = SSEStreamingResponse.from_token_generator(tokens(), request=request)
        results = []
        async for chunk in response.body_iterator:
            results.append(chunk)
            if len(results) >= 2:
                break

        assert len(results) >= 1
