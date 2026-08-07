"""Workflow definition and run-record storage.

Extracted from api/api/workflows.py so both the HTTP layer and the LangGraph
engine (api/core/workflow/) can share storage without circular imports.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from api.services.local_store import LocalStore

_workflow_store = LocalStore("workflows.json")
_workflow_store_data = _workflow_store.read()
_workflows = _workflow_store_data.get("workflows", {})
_workflow_run_store = LocalStore("workflow_runs.json")
_workflow_run_store_data = _workflow_run_store.read()
_workflow_runs = _workflow_run_store_data.get("runs", {})
_workflow_run_db_path = os.path.join(
    os.path.dirname(__file__), "..", "data", "workflow_runs.sqlite3"
)


def persist_workflows() -> None:
    _workflow_store.write({"workflows": _workflows})


def _persist_workflow_runs() -> None:
    _workflow_run_store.write({"runs": _workflow_runs})


def _run_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(_workflow_run_db_path)), exist_ok=True)
    connection = sqlite3.connect(_workflow_run_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def _sync_workflow_runs_to_sqlite() -> None:
    connection = _run_db_connection()
    try:
        for run in _workflow_runs.values():
            connection.execute(
                """
                INSERT INTO workflow_runs (id, workflow_id, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workflow_id=excluded.workflow_id,
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    run["id"],
                    run["workflow_id"],
                    run.get("status", "running"),
                    json.dumps(run, ensure_ascii=False),
                    run.get("updated_at") or datetime.utcnow().isoformat(),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def persist_workflow_run_record(run_record: Dict[str, Any]) -> None:
    _workflow_runs[run_record["id"]] = run_record
    _persist_workflow_runs()
    _sync_workflow_runs_to_sqlite()


def load_workflow_run(run_id: str) -> Optional[Dict[str, Any]]:
    if run_id in _workflow_runs:
        return _workflow_runs[run_id]
    connection = _run_db_connection()
    try:
        row = connection.execute(
            "SELECT payload_json FROM workflow_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        run = json.loads(row["payload_json"])
        _workflow_runs[run_id] = run
        return run
    finally:
        connection.close()


def list_workflow_runs_for(workflow_id: str) -> List[Dict[str, Any]]:
    connection = _run_db_connection()
    try:
        rows = connection.execute(
            "SELECT payload_json FROM workflow_runs WHERE workflow_id = ? ORDER BY updated_at DESC",
            (workflow_id,),
        ).fetchall()
        runs = [json.loads(row["payload_json"]) for row in rows]
        for run in runs:
            _workflow_runs[run["id"]] = run
        return runs
    finally:
        connection.close()


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


_sync_workflow_runs_to_sqlite()
