"""Workflow definition and run-record storage.

Extracted from api/api/workflows.py so both the HTTP layer and the LangGraph
engine (api/core/workflow/) can share storage without circular imports.

All records live in LocalStore namespaces, so they follow the active
business-store backend (local JSON or MySQL) transparently.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from api.services.local_store import LocalStore

_workflow_store = LocalStore("workflows.json")
_workflow_store_data = _workflow_store.read()
_workflows = _workflow_store_data.get("workflows", {})
_workflow_run_store = LocalStore("workflow_runs.json")
_workflow_run_store_data = _workflow_run_store.read()
_workflow_runs = _workflow_run_store_data.get("runs", {})


def persist_workflows() -> None:
    _workflow_store.write({"workflows": _workflows})


def persist_workflow_run_record(run_record: Dict[str, Any]) -> None:
    _workflow_runs[run_record["id"]] = run_record
    _workflow_run_store.write({"runs": _workflow_runs})


def load_workflow_run(run_id: str) -> Optional[Dict[str, Any]]:
    if run_id in _workflow_runs:
        return _workflow_runs[run_id]
    # Refresh from the store (e.g. after a restart or backend switch).
    _workflow_runs.update(_workflow_run_store.read().get("runs", {}))
    return _workflow_runs.get(run_id)


def list_workflow_runs_for(workflow_id: str) -> List[Dict[str, Any]]:
    _workflow_runs.update(_workflow_run_store.read().get("runs", {}))
    runs = [
        run
        for run in _workflow_runs.values()
        if run.get("workflow_id") == workflow_id
    ]
    runs.sort(key=lambda run: run.get("updated_at") or "", reverse=True)
    return runs


def workflow_versions(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    versions = workflow.setdefault("versions", [])
    if not isinstance(versions, list):
        workflow["versions"] = []
    return workflow["versions"]


def record_workflow_version(workflow: Dict[str, Any]) -> None:
    versions = workflow_versions(workflow)
    versions.append(
        {
            "version": len(versions) + 1,
            "dsl": workflow.get("dsl") or {},
            "created_at": datetime.utcnow().isoformat(),
        }
    )
