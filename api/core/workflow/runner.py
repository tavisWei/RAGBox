"""Execution entrypoints bridging the FastAPI layer and LangGraph."""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import uuid4

from langgraph.types import Command

from api.services import workflow_store

from . import dsl
from .checkpointer import get_checkpointer
from .compiler import compile_workflow
from .nodes import NodeExecutionError, failed_trace
from .state import EMPTY_RESUME_KEY, FAILED_CONTEXT_KEY


def _config(run_id: str, node_count: int) -> Dict[str, Any]:
    return {
        "configurable": {"thread_id": run_id},
        "recursion_limit": max(100, node_count * 4),
    }


def _interrupt_payload(state) -> Optional[Dict[str, Any]]:
    for task in getattr(state, "tasks", None) or []:
        for item in getattr(task, "interrupts", None) or []:
            value = getattr(item, "value", None)
            if isinstance(value, dict):
                return value
    return None


def _assemble_execution(validated_dsl: Dict[str, Any], state) -> Dict[str, Any]:
    """Build the legacy-shaped execution result from a checkpointed state."""
    values = state.values or {}
    context = dict(values.get("context") or {})
    failed_node_id = context.pop(FAILED_CONTEXT_KEY, None)
    traces = list(values.get("traces") or [])
    paused = bool(getattr(state, "next", None))
    if paused:
        interrupt_info = _interrupt_payload(state)
        if interrupt_info:
            now = datetime.utcnow().isoformat()
            traces.append(
                {
                    "node_id": interrupt_info.get("node_id"),
                    "node_type": interrupt_info.get("node_type", "approval"),
                    "title": interrupt_info.get("title") or "approval",
                    "status": "paused",
                    "input": dict(context),
                    "output": None,
                    "pause_key": interrupt_info.get("pause_key"),
                    "started_at": now,
                    "finished_at": now,
                }
            )
    nodes = dsl.node_by_id(validated_dsl)
    return {
        "traces": traces,
        "final_output": dsl.terminal_output_from_traces(traces, nodes),
        "executed_node_ids": [
            trace["node_id"]
            for trace in traces
            if trace.get("status") in {"succeeded", "fallback"}
        ],
        "status": "failed" if failed_node_id else "succeeded",
        "paused": paused,
        "failed_node_id": failed_node_id,
        "context": context,
    }


async def execute(
    workflow_dsl: Dict[str, Any], inputs: Dict[str, Any], run_id: str
) -> Dict[str, Any]:
    """Run a workflow to completion (or an approval interrupt).

    A node whose LangGraph RetryPolicy attempts are exhausted raises
    NodeExecutionError; it is converted here into the legacy-shaped failed
    execution (failed trace + status) instead of propagating.
    """
    validated = dsl.validate_dsl(workflow_dsl)
    context = dict(inputs or {})
    dsl.apply_workflow_globals(validated, context)
    checkpointer = await get_checkpointer()
    graph = compile_workflow(validated, checkpointer)
    config = _config(run_id, len(validated["nodes"]))
    exhausted: Optional[NodeExecutionError] = None
    try:
        await graph.ainvoke({"context": context, "traces": []}, config)
    except NodeExecutionError as exc:
        exhausted = exc
    state = await graph.aget_state(config)
    execution = _assemble_execution(validated, state)
    if exhausted is not None:
        execution["traces"] = execution["traces"] + [
            failed_trace(exhausted.node_spec, exhausted.context, exhausted.cause)
        ]
        execution["status"] = "failed"
        execution["failed_node_id"] = exhausted.node_spec.get("id")
    return execution


async def resume(
    workflow_dsl: Dict[str, Any], run_record: Dict[str, Any], inputs: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Resume an interrupted run. Returns None when the run has no LangGraph
    checkpoint (the caller turns that into a 400)."""
    validated = dsl.validate_dsl(workflow_dsl)
    checkpointer = await get_checkpointer()
    graph = compile_workflow(validated, checkpointer)
    config = _config(run_record["id"], len(validated["nodes"]))
    state = await graph.aget_state(config)
    if not state.values.get("traces") and not getattr(state, "next", None):
        return None
    resume_value = inputs or {EMPTY_RESUME_KEY: True}
    exhausted: Optional[NodeExecutionError] = None
    try:
        await graph.ainvoke(Command(resume=resume_value), config)
    except NodeExecutionError as exc:
        exhausted = exc
    state = await graph.aget_state(config)
    execution = _assemble_execution(validated, state)
    if exhausted is not None:
        execution["traces"] = execution["traces"] + [
            failed_trace(exhausted.node_spec, exhausted.context, exhausted.cause)
        ]
        execution["status"] = "failed"
        execution["failed_node_id"] = exhausted.node_spec.get("id")
    return execution


async def stream(
    workflow_dsl: Dict[str, Any], workflow_id: str, inputs: Dict[str, Any]
) -> AsyncGenerator[str, None]:
    """Run a workflow, yielding SSE frames per node and a final result frame.

    Frame protocol:
      data: {"type": "trace", "trace": {...}}
      data: {"type": "result", "output": {...}}
    """
    validated = dsl.validate_dsl(workflow_dsl)
    context = dict(inputs or {})
    dsl.apply_workflow_globals(validated, context)
    checkpointer = await get_checkpointer()
    graph = compile_workflow(validated, checkpointer)

    run_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    run_record = {
        "id": run_id,
        "workflow_id": workflow_id,
        "status": "running",
        "inputs": inputs or {},
        "context": context,
        "traces": [],
        "executed_node_ids": [],
        "result": None,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
    }
    workflow_store.persist_workflow_run_record(run_record)
    config = _config(run_id, len(validated["nodes"]))
    try:
        async for chunk in graph.astream(
            {"context": context, "traces": []}, config, stream_mode="updates"
        ):
            for _node_id, update in chunk.items():
                for trace in (update or {}).get("traces") or []:
                    frame = {"type": "trace", "trace": trace}
                    yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
        state = await graph.aget_state(config)
        execution = _assemble_execution(validated, state)
    except Exception:
        run_record["status"] = "failed"
        run_record["updated_at"] = datetime.utcnow().isoformat()
        run_record["finished_at"] = run_record["updated_at"]
        workflow_store.persist_workflow_run_record(run_record)
        raise

    run_record["status"] = "paused" if execution.get("paused") else execution["status"]
    run_record["context"] = execution["context"]
    run_record["traces"] = execution["traces"]
    run_record["executed_node_ids"] = execution["executed_node_ids"]
    run_record["result"] = execution["final_output"]
    run_record["failed_node_id"] = execution["failed_node_id"]
    run_record["updated_at"] = datetime.utcnow().isoformat()
    run_record["finished_at"] = run_record["updated_at"]
    workflow_store.persist_workflow_run_record(run_record)

    output = {
        "message": "Workflow executed",
        "inputs": inputs or {},
        "run_id": run_id,
        "status": run_record["status"],
        "result": run_record["result"],
        "context": run_record["context"],
        "traces": run_record["traces"],
    }
    frame = {"type": "result", "output": output}
    yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
