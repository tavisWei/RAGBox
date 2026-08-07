"""Workflow HTTP API: CRUD, versioning, run/stream/resume.

All execution lives in api.core.workflow (LangGraph engine); storage lives in
api.services.workflow_store. This module only exposes the HTTP surface plus
backwards-compatible aliases used by tests.
"""

import urllib.request  # noqa: F401  (kept as a monkeypatch seam for tests)
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.api.deps import get_current_user
from api.core.workflow import executor, runner
from api.core.workflow.dsl import default_dsl, validate_dsl
from api.core.workflow.tools import TOOL_REGISTRY
from api.services.workflow_store import (
    _workflows,
    list_workflow_runs_for,
    load_workflow_run,
    persist_workflow_run_record,
    persist_workflows,
    record_workflow_version,
    workflow_versions,
)

router = APIRouter()


class WorkflowCreate(BaseModel):
    app_id: str
    name: str
    description: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dsl: Optional[dict] = None


class WorkflowRun(BaseModel):
    inputs: Optional[dict] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class WorkflowResume(BaseModel):
    inputs: Optional[dict] = None


class WorkflowOut(BaseModel):
    id: str
    app_id: str
    name: str
    description: Optional[str] = None
    dsl: dict = {}


# ---------------------------------------------------------------------------
# Backwards-compatible aliases (tests patch/call these on this module).
# ---------------------------------------------------------------------------
_validate_dsl = validate_dsl
_default_dsl = default_dsl
_resolve_model = executor.resolve_model
RAGService = executor.RAGService


async def _execute_node(node, context, payload=None):
    return await executor.execute_node(node, context)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/workflows/tools")
async def list_workflow_tools(user: dict = Depends(get_current_user)):
    """Tools available to workflow tool nodes (LangChain tool registry)."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "args_schema": tool.args,
        }
        for tool in TOOL_REGISTRY.values()
    ]


@router.get("/workflows", response_model=List[WorkflowOut])
async def list_workflows(
    app_id: Optional[str] = None, user: dict = Depends(get_current_user)
):
    items = list(_workflows.values())
    if app_id:
        items = [item for item in items if item["app_id"] == app_id]
    return [WorkflowOut(**item) for item in items]


@router.post("/workflows", response_model=WorkflowOut)
async def create_workflow(
    payload: WorkflowCreate, user: dict = Depends(get_current_user)
):
    workflow_id = str(uuid4())
    workflow = {
        "id": workflow_id,
        "app_id": payload.app_id,
        "name": payload.name,
        "description": payload.description,
        "dsl": default_dsl(),
    }
    _workflows[workflow_id] = workflow
    persist_workflows()
    return WorkflowOut(**workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: str, user: dict = Depends(get_current_user)):
    workflow = _workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return WorkflowOut(**workflow)


@router.get("/workflows/{workflow_id}/versions")
async def list_workflow_versions(
    workflow_id: str, user: dict = Depends(get_current_user)
):
    workflow = _workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return workflow_versions(workflow)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(get_current_user)):
    if workflow_id not in _workflows:
        raise HTTPException(404, "Workflow not found")
    del _workflows[workflow_id]
    persist_workflows()
    return {"message": "Workflow deleted"}


@router.put("/workflows/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: str, payload: WorkflowUpdate, user: dict = Depends(get_current_user)
):
    workflow = _workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    if payload.name is not None:
        workflow["name"] = payload.name
    if payload.description is not None:
        workflow["description"] = payload.description
    if payload.dsl is not None:
        record_workflow_version(workflow)
        workflow["dsl"] = validate_dsl(payload.dsl)
    persist_workflows()
    return WorkflowOut(**workflow)


@router.get("/workflows/{workflow_id}/runs")
async def list_workflow_runs(workflow_id: str, user: dict = Depends(get_current_user)):
    if workflow_id not in _workflows:
        raise HTTPException(404, "Workflow not found")
    return list_workflow_runs_for(workflow_id)


@router.get("/workflows/{workflow_id}/runs/{run_id}")
async def get_workflow_run(
    workflow_id: str, run_id: str, user: dict = Depends(get_current_user)
):
    run = load_workflow_run(run_id)
    if not run or run.get("workflow_id") != workflow_id:
        raise HTTPException(404, "Workflow run not found")
    return run


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(
    workflow_id: str, payload: WorkflowRun, user: dict = Depends(get_current_user)
):
    workflow = _workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    dsl_payload = validate_dsl(workflow.get("dsl") or {})
    run_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    run_record = {
        "id": run_id,
        "workflow_id": workflow_id,
        "status": "running",
        "inputs": payload.inputs or {},
        "context": dict(payload.inputs or {}),
        "traces": [],
        "executed_node_ids": [],
        "result": None,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
    }
    persist_workflow_run_record(run_record)
    try:
        execution = await runner.execute(dsl_payload, payload.inputs or {}, run_id)
    except HTTPException:
        run_record["status"] = "failed"
        run_record["updated_at"] = datetime.utcnow().isoformat()
        run_record["finished_at"] = run_record["updated_at"]
        persist_workflow_run_record(run_record)
        raise
    except Exception as exc:
        run_record["status"] = "failed"
        run_record["updated_at"] = datetime.utcnow().isoformat()
        run_record["finished_at"] = run_record["updated_at"]
        persist_workflow_run_record(run_record)
        raise HTTPException(500, str(exc)) from exc
    run_record["status"] = "paused" if execution.get("paused") else execution["status"]
    run_record["context"] = execution["context"]
    run_record["traces"] = execution["traces"]
    run_record["executed_node_ids"] = execution["executed_node_ids"]
    run_record["result"] = execution["final_output"]
    run_record["failed_node_id"] = execution["failed_node_id"]
    run_record["updated_at"] = datetime.utcnow().isoformat()
    run_record["finished_at"] = run_record["updated_at"]
    persist_workflow_run_record(run_record)
    return {
        "result": "success",
        "workflow_id": workflow_id,
        "run_id": run_id,
        "output": {
            "message": "Workflow executed",
            "inputs": payload.inputs or {},
            "run_id": run_id,
            "status": run_record["status"],
            "result": run_record["result"],
            "context": run_record["context"],
            "traces": run_record["traces"],
        },
    }


@router.post("/workflows/{workflow_id}/run/stream")
async def run_workflow_stream(
    workflow_id: str, payload: WorkflowRun, user: dict = Depends(get_current_user)
):
    workflow = _workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    dsl_payload = validate_dsl(workflow.get("dsl") or {})

    async def event_stream():
        async for frame in runner.stream(
            dsl_payload, workflow_id, payload.inputs or {}
        ):
            yield frame

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/workflows/{workflow_id}/runs/{run_id}/resume")
async def resume_workflow_run(
    workflow_id: str,
    run_id: str,
    payload: WorkflowResume,
    user: dict = Depends(get_current_user),
):
    workflow = _workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    run_record = load_workflow_run(run_id)
    if not run_record or run_record.get("workflow_id") != workflow_id:
        raise HTTPException(404, "Workflow run not found")
    if run_record.get("status") == "succeeded":
        return run_record
    execution = await runner.resume(
        validate_dsl(workflow.get("dsl") or {}), run_record, payload.inputs or {}
    )
    if execution is None:
        raise HTTPException(
            400, "Workflow run has no checkpoint and cannot be resumed"
        )
    run_record["status"] = "paused" if execution.get("paused") else execution["status"]
    run_record["context"] = execution["context"]
    run_record["traces"] = execution["traces"]
    run_record["executed_node_ids"] = execution["executed_node_ids"]
    run_record["result"] = execution["final_output"]
    run_record["failed_node_id"] = execution["failed_node_id"]
    run_record["updated_at"] = datetime.utcnow().isoformat()
    run_record["finished_at"] = run_record["updated_at"]
    persist_workflow_run_record(run_record)
    return run_record
