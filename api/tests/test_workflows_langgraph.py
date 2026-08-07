"""Behavior tests for the LangGraph workflow engine.

The endpoint-level flows are covered by test_workflows.py; this file tests
the LangGraph runner directly with golden assertions.
"""

import json
from uuid import uuid4

import pytest

from api.core.workflow import runner
from api.core.workflow.checkpointer import close_all_checkpointers


@pytest.fixture(autouse=True)
async def _close_checkpointers():
    # aiosqlite spawns a non-daemon thread per connection; closing all savers
    # keeps the pytest process exit clean.
    yield
    await close_all_checkpointers()


def _parallel_dsl() -> dict:
    return {
        "globals": {"suffix": "!"},
        "settings": {"timeout": 60, "parallelism": 4, "on_error": "stop"},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "left",
                "type": "template",
                "data": {"template": "L{{input}}", "output_key": "left_out"},
            },
            {
                "id": "right",
                "type": "template",
                "data": {"template": "R{{input}}", "output_key": "right_out"},
            },
            {
                "id": "merge",
                "type": "merge",
                "data": {
                    "sources": ["left_out", "right_out"],
                    "output_key": "merged",
                },
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "{{merged}}{{suffix}}", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-left", "source": "start", "target": "left"},
            {"id": "start-right", "source": "start", "target": "right"},
            {"id": "left-merge", "source": "left", "target": "merge"},
            {"id": "right-merge", "source": "right", "target": "merge"},
            {"id": "merge-end", "source": "merge", "target": "end"},
        ],
    }


def _trace_map(traces) -> dict:
    return {trace["node_id"]: (trace["status"], trace["output"]) for trace in traces}


async def test_parallel_fanout_merge_golden() -> None:
    dsl = _parallel_dsl()
    result = await runner.execute(dsl, {"input": "x"}, str(uuid4()))

    assert result["status"] == "succeeded"
    assert result["final_output"] == "{'left_out': 'Lx', 'right_out': 'Rx'}!"
    assert _trace_map(result["traces"]) == {
        "start": ("succeeded", "x"),
        "left": ("succeeded", "Lx"),
        "right": ("succeeded", "Rx"),
        "merge": ("succeeded", {"left_out": "Lx", "right_out": "Rx"}),
        "end": ("succeeded", "{'left_out': 'Lx', 'right_out': 'Rx'}!"),
    }
    # Parallel branches both contributed to the context without clobbering.
    assert result["context"]["left_out"] == "Lx"
    assert result["context"]["right_out"] == "Rx"


async def test_failed_node_stops_graph_and_marks_run_failed() -> None:
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "broken",
                "type": "code",
                "data": {"expression": "context.__class__", "output_key": "boom"},
            },
            {"id": "end", "type": "end", "data": {"answer": "done"}},
        ],
        "edges": [
            {"id": "start-broken", "source": "start", "target": "broken"},
            {"id": "broken-end", "source": "broken", "target": "end"},
        ],
    }
    result = await runner.execute(dsl, {"input": "x"}, str(uuid4()))

    assert result["status"] == "failed"
    assert result["failed_node_id"] == "broken"
    assert _trace_map(result["traces"]) == {
        "start": ("succeeded", "x"),
        "broken": ("failed", None),
    }
    # Internal failure marker must not leak into the user-visible context.
    assert runner.FAILED_CONTEXT_KEY not in result["context"]


def _approval_dsl() -> dict:
    return {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "approval",
                "type": "approval",
                "data": {"approval_key": "approved", "output_key": "approval_output"},
            },
            {
                "id": "end",
                "type": "end",
                "data": {
                    "answer": "{{input}} -> {{approval_output}}",
                    "output_key": "answer",
                },
            },
        ],
        "edges": [
            {"id": "start-approval", "source": "start", "target": "approval"},
            {"id": "approval-end", "source": "approval", "target": "end"},
        ],
    }


async def test_approval_interrupts_then_resume_completes() -> None:
    dsl = _approval_dsl()
    run_id = str(uuid4())

    first = await runner.execute(dsl, {"input": "x"}, run_id)
    assert first["paused"] is True
    paused_traces = [t for t in first["traces"] if t["status"] == "paused"]
    assert len(paused_traces) == 1
    assert paused_traces[0]["node_id"] == "approval"
    assert paused_traces[0]["pause_key"] == "approved"

    resumed = await runner.resume(dsl, {"id": run_id}, {"approved": True})
    assert resumed is not None
    assert resumed["paused"] is False
    assert resumed["status"] == "succeeded"
    assert resumed["final_output"] == "x -> True"


async def test_approval_resume_without_decision_means_rejected() -> None:
    dsl = _approval_dsl()
    run_id = str(uuid4())
    first = await runner.execute(dsl, {"input": "x"}, run_id)
    assert first["paused"] is True

    resumed = await runner.resume(dsl, {"id": run_id}, {})
    assert resumed["status"] == "succeeded"
    assert resumed["final_output"] == "x -> False"


async def test_resume_returns_none_without_checkpoint() -> None:
    result = await runner.resume(_approval_dsl(), {"id": str(uuid4())}, {})
    assert result is None


async def test_stream_emits_trace_frames_then_result_frame() -> None:
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "echo {{input}}", "output_key": "answer"},
            },
        ],
        "edges": [{"id": "start-end", "source": "start", "target": "end"}],
    }
    frames = [
        frame
        async for frame in runner.stream(dsl, f"wf-{uuid4()}", {"input": "hi"})
    ]
    assert len(frames) >= 3  # start trace + end trace + result
    payloads = [
        json.loads(frame.removeprefix("data: ").strip()) for frame in frames
    ]
    assert all(payload["type"] == "trace" for payload in payloads[:-1])
    assert [p["trace"]["node_id"] for p in payloads[:-1]] == ["start", "end"]
    result = payloads[-1]
    assert result["type"] == "result"
    assert result["output"]["status"] == "succeeded"
    assert result["output"]["result"] == "echo hi"
    assert result["output"]["traces"]  # full trace list in the result frame


# ---------------------------------------------------------------------------
# LangChain adoption: tool node, tools endpoint, chat-model mapping
# ---------------------------------------------------------------------------


async def test_tool_node_invokes_registered_langchain_tool() -> None:
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "calc",
                "type": "tool",
                "data": {"tool": "calculator", "template": "{{input}}", "output_key": "calc_out"},
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "calc={{calc_out}}", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-calc", "source": "start", "target": "calc"},
            {"id": "calc-end", "source": "calc", "target": "end"},
        ],
    }
    result = await runner.execute(dsl, {"input": "1 + 2 * 3"}, str(uuid4()))
    assert result["status"] == "succeeded"
    assert result["final_output"] == "calc=7"


async def test_tool_node_template_mode_unchanged() -> None:
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "tool",
                "type": "tool",
                "data": {"tool": "template", "template": "echo {{input}}", "output_key": "tool_output"},
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "{{tool_output}}", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-tool", "source": "start", "target": "tool"},
            {"id": "tool-end", "source": "tool", "target": "end"},
        ],
    }
    result = await runner.execute(dsl, {"input": "hi"}, str(uuid4()))
    assert result["final_output"] == "echo hi"


async def test_tool_node_unknown_tool_fails() -> None:
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "tool",
                "type": "tool",
                "data": {"tool": "does_not_exist", "template": "x", "output_key": "tool_output"},
            },
            {"id": "end", "type": "end", "data": {"answer": "done"}},
        ],
        "edges": [
            {"id": "start-tool", "source": "start", "target": "tool"},
            {"id": "tool-end", "source": "tool", "target": "end"},
        ],
    }
    result = await runner.execute(dsl, {"input": "x"}, str(uuid4()))
    assert result["status"] == "failed"
    failed = [t for t in result["traces"] if t["status"] == "failed"]
    assert failed and "Unknown tool" in failed[0]["error"]


def test_workflow_tools_endpoint_lists_registry() -> None:
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/workflows/tools", headers=headers)
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()}
    assert {"calculator", "http_get", "current_time"} <= names


def test_build_chat_model_provider_mapping() -> None:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI

    from api.core.workflow.llm import build_chat_model

    openai_model = build_chat_model(
        {"provider": "openai", "model": "gpt-4o", "api_key": "k", "base_url": None},
        max_tokens=10,
        temperature=0.5,
        timeout=30,
    )
    assert isinstance(openai_model, ChatOpenAI)

    compat_model = build_chat_model(
        {
            "provider": "minimax",
            "model": "abab6.5",
            "api_key": "k",
            "base_url": "http://example.test",
        },
        max_tokens=10,
        temperature=0.5,
        timeout=30,
    )
    assert isinstance(compat_model, ChatOpenAI)

    ollama_model = build_chat_model(
        {"provider": "ollama", "model": "llama3", "api_key": None, "base_url": None},
        max_tokens=10,
        temperature=0.5,
        timeout=30,
    )
    assert isinstance(ollama_model, ChatOllama)

    with pytest.raises(Exception):
        build_chat_model(
            {"provider": "unknown", "model": "m", "api_key": None, "base_url": None},
            max_tokens=10,
            temperature=0.5,
            timeout=30,
        )
