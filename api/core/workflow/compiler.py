"""Compile the existing workflow DSL into a LangGraph StateGraph."""

import hashlib
import json
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from . import dsl
from .nodes import make_node, max_attempts
from .state import FAILED_CONTEXT_KEY, WorkflowState

_compiled_cache: Dict[Any, Any] = {}


def _halted(state: Dict[str, Any]) -> bool:
    return bool((state.get("context") or {}).get(FAILED_CONTEXT_KEY))


def compile_workflow(workflow_dsl: Dict[str, Any], checkpointer=None):
    """Build (and cache) a CompiledStateGraph for a validated workflow DSL.

    The cache key includes the checkpointer object itself (not id()): the
    dict holds a strong reference, so a closed saver can never be recycled
    into a stale hit. Savers are bound to their event loop — see
    checkpointer.py.
    """
    validated = dsl.validate_dsl(workflow_dsl)
    dsl_hash = hashlib.sha256(
        json.dumps(validated, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    cache_key = (dsl_hash, checkpointer)
    if cache_key in _compiled_cache:
        return _compiled_cache[cache_key]

    settings = dsl.workflow_settings(validated)
    builder = StateGraph(WorkflowState)
    for node in validated["nodes"]:
        attempts = max_attempts(node)
        builder.add_node(
            node["id"],
            make_node(node, settings),
            retry_policy=(
                RetryPolicy(max_attempts=attempts, backoff_factor=2, max_interval=5)
                if attempts > 1
                else None
            ),
            timeout=float(settings["timeout"]),
        )

    outgoing: Dict[str, list] = {}
    for edge in validated["edges"]:
        outgoing.setdefault(edge["source"], []).append(edge)

    for node in validated["nodes"]:
        node_id = node["id"]
        node_type = node.get("type")
        edges = outgoing.get(node_id, [])
        if node_type in dsl.TERMINAL_NODE_TYPES:
            builder.add_edge(node_id, END)
            continue
        if not edges:
            continue
        if node_type == "condition":
            data = dsl.node_data(node)
            output_key = data.get("output_key", "condition_result")
            targets = {edge["label"]: edge["target"] for edge in edges}

            def condition_router(
                state: Dict[str, Any], _key=output_key, _targets=targets
            ):
                if _halted(state):
                    return END
                context = state.get("context") or {}
                return "true" if bool(context.get(_key)) else "false"

            builder.add_conditional_edges(
                node_id, condition_router, {**targets, END: END}
            )
        else:
            targets = [edge["target"] for edge in edges]

            def router(state: Dict[str, Any], _targets=targets):
                if _halted(state):
                    return END
                return _targets

            builder.add_conditional_edges(
                node_id, router, {target: target for target in targets} | {END: END}
            )

    for node in validated["nodes"]:
        if node.get("type") == "start":
            builder.add_edge(START, node["id"])

    compiled = builder.compile(checkpointer=checkpointer)
    _compiled_cache[cache_key] = compiled
    return compiled
