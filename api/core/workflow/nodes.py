"""LangGraph node factory wrapping the per-node executors.

Retries and timeouts are NOT handled here — the compiler attaches a LangGraph
RetryPolicy / timeout to each node. This wrapper handles the approval
interrupt, executes the node, and converts the result into a state delta.
"""

from datetime import datetime
from typing import Any, Callable, Dict

from fastapi import HTTPException
from langgraph.types import interrupt

from . import dsl, executor
from .state import EMPTY_RESUME_KEY, FAILED_CONTEXT_KEY


class NodeExecutionError(Exception):
    """Node failure after the RetryPolicy attempts were exhausted.

    Carries everything the runner needs to record the legacy-shaped failed
    trace without the exception ever becoming a state update.
    """

    def __init__(self, node_spec: Dict[str, Any], context: Dict[str, Any], cause: HTTPException):
        self.node_spec = node_spec
        self.context = context
        self.cause = cause
        super().__init__(str(cause.detail))


def max_attempts(node_spec: Dict[str, Any]) -> int:
    return int(dsl.node_data(node_spec).get("retry", 0) or 0) + 1


def failed_trace(node_spec: Dict[str, Any], context: Dict[str, Any], exc: HTTPException) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "node_id": node_spec.get("id"),
        "node_type": node_spec.get("type"),
        "title": node_spec.get("title") or node_spec.get("type"),
        "status": "failed",
        "input": dict(context),
        "output": None,
        "error": exc.detail,
        "attempt": max_attempts(node_spec),
        "started_at": now,
        "finished_at": now,
    }


def make_node(node_spec: Dict[str, Any], settings: Dict[str, Any]) -> Callable:
    """Build a LangGraph node function for one DSL node spec."""
    node_id = node_spec["id"]
    node_type = node_spec.get("type")

    async def node_fn(state: Dict[str, Any]) -> Dict[str, Any]:
        data = dsl.node_data(node_spec)
        context = dict(state.get("context") or {})
        context.pop(FAILED_CONTEXT_KEY, None)
        before = dict(context)

        if node_type == "approval":
            approval_key = data.get("approval_key", "approved")
            if approval_key not in context:
                resume_inputs = interrupt(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "title": node_spec.get("title")
                        or data.get("title")
                        or node_type,
                        "pause_key": approval_key,
                    }
                )
                if isinstance(resume_inputs, dict):
                    resume_inputs = dict(resume_inputs)
                    resume_inputs.pop(EMPTY_RESUME_KEY, None)
                    context.update(resume_inputs)
                if approval_key not in context:
                    # Mirror the legacy resume semantics: resuming without a
                    # decision value means the approval is rejected (False).
                    context[approval_key] = False

        try:
            # Module-attribute call keeps the monkeypatch seam for tests.
            # HTTPException propagates so the RetryPolicy can retry; the
            # runner turns the final NodeExecutionError into a failed trace.
            trace = await executor.execute_node(node_spec, context)
            trace["attempt"] = 1
        except HTTPException as exc:
            raise NodeExecutionError(node_spec, context, exc) from exc
        delta = {
            key: value
            for key, value in context.items()
            if key not in before or before[key] != value
        }
        if trace["status"] == "failed":
            delta[FAILED_CONTEXT_KEY] = node_id
        update: Dict[str, Any] = {"traces": [trace]}
        if delta:
            update["context"] = delta
        return update

    return node_fn
