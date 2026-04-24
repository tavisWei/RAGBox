import asyncio
import ast
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.local_store import LocalStore
from api.services.llm_service import ChatConfig, ChatMessage, LLMService
from api.services.model_provider_service import model_provider_service
from api.services.rag_service import RAGService
from .deps import get_current_user

router = APIRouter()

_workflow_store = LocalStore("workflows.json")
_workflow_store_data = _workflow_store.read()
_workflows = _workflow_store_data.get("workflows", {})
_workflow_run_store = LocalStore("workflow_runs.json")
_workflow_run_store_data = _workflow_run_store.read()
_workflow_runs = _workflow_run_store_data.get("runs", {})
_workflow_run_db_path = os.path.join(
    os.path.dirname(__file__), "..", "data", "workflow_runs.sqlite3"
)
WORKFLOW_LLM_TIMEOUT_SECONDS = 60

NODE_TYPES = {
    "start",
    "template",
    "llm",
    "knowledge",
    "condition",
    "variable",
    "http",
    "code",
    "iteration",
    "workflow",
    "merge",
    "tool",
    "approval",
    "answer",
    "question_classifier",
    "parameter_extractor",
    "list_operator",
    "document_extractor",
    "end",
}
TERMINAL_NODE_TYPES = {"end", "answer"}


def _persist_workflows() -> None:
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


def _persist_workflow_run_record(run_record: Dict[str, Any]) -> None:
    _workflow_runs[run_record["id"]] = run_record
    _persist_workflow_runs()
    _sync_workflow_runs_to_sqlite()


def _load_workflow_run(run_id: str) -> Optional[Dict[str, Any]]:
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


def _list_workflow_runs_for(workflow_id: str) -> List[Dict[str, Any]]:
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


_sync_workflow_runs_to_sqlite()


def _workflow_versions(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    versions = workflow.setdefault("versions", [])
    if not isinstance(versions, list):
        workflow["versions"] = []
    return workflow["versions"]


def _record_workflow_version(workflow: Dict[str, Any]) -> None:
    versions = _workflow_versions(workflow)
    versions.append(
        {
            "version": len(versions) + 1,
            "dsl": workflow.get("dsl") or {},
            "created_at": datetime.utcnow().isoformat(),
        }
    )


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


def _default_dsl() -> Dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 80, "y": 180},
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "type": "string", "required": True}],
                },
            },
            {
                "id": "end",
                "type": "end",
                "title": "结束",
                "position": {"x": 760, "y": 180},
                "data": {"answer": "{{input}}"},
            },
        ],
        "edges": [{"id": "start-end", "source": "start", "target": "end"}],
        "globals": {},
        "settings": {"timeout": 60, "parallelism": 4, "on_error": "stop"},
    }


def _node_data(node: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(node.get("data") or {})
    for key, value in node.items():
        if key not in {"id", "type", "title", "position", "data"}:
            data.setdefault(key, value)
    return data


def _render_template(template: Any, context: Dict[str, Any]) -> str:
    output = str(template or "")
    for key, value in context.items():
        output = output.replace("{{" + key + "}}", str(value))
    return output


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _cast_input_value(value: Any, value_type: Optional[str]) -> Any:
    if value_type in {None, "", "string"}:
        return "" if value is None else str(value)
    if value_type == "number":
        return float(value)
    if value_type == "integer":
        return int(value)
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}
    if value_type == "json":
        if isinstance(value, (dict, list)):
            return value
        return json.loads(str(value))
    return value


def _resolve_secret(template: Any, context: Dict[str, Any]) -> str:
    rendered = _render_template(template, context)

    def replacer(match: re.Match) -> str:
        return os.getenv(match.group(1), "")

    return re.sub(r"\{\{secret:([A-Z0-9_]+)\}\}", replacer, rendered)


def _safe_eval_expression(expression: str, context: Dict[str, Any]) -> Any:
    allowed_calls = {"len", "str", "int", "float", "bool", "sum", "min", "max"}
    allowed_methods = {"get", "upper", "lower", "strip", "split", "replace"}
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in allowed_calls:
                    raise HTTPException(400, "Code node call is not allowed")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr not in allowed_methods:
                    raise HTTPException(400, "Code node call is not allowed")
            else:
                raise HTTPException(400, "Code node call is not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr not in allowed_methods:
                raise HTTPException(400, "Code node attribute access is not allowed")
        elif isinstance(
            node,
            (ast.Import, ast.ImportFrom, ast.Lambda, ast.FunctionDef, ast.ClassDef),
        ):
            raise HTTPException(400, "Code node syntax is not allowed")
    safe_globals = {
        "__builtins__": {},
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "sum": sum,
        "min": min,
        "max": max,
    }
    return eval(
        compile(tree, "<workflow-code>", "eval"), safe_globals, {"context": context}
    )


def _apply_start_inputs(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    variables = data.get("variables") or []
    if not isinstance(variables, list):
        raise HTTPException(400, "Start node variables must be an array")
    for variable in variables:
        if not isinstance(variable, dict):
            raise HTTPException(400, "Start node variable must be an object")
        key = variable.get("key")
        if not key:
            raise HTTPException(400, "Start node variable key is required")
        if key not in context and "default" in variable:
            context[key] = _cast_input_value(
                variable.get("default"), variable.get("type")
            )
        if variable.get("required") and key not in context:
            raise HTTPException(400, f"Missing required workflow input: {key}")
        if key in context:
            context[key] = _cast_input_value(context[key], variable.get("type"))


def _evaluate_condition(data: Dict[str, Any], context: Dict[str, Any]) -> bool:
    left = _render_template(data.get("left"), context)
    operator = data.get("operator", "contains")
    right = _render_template(data.get("right"), context)
    if operator == "equals":
        return left == right
    if operator == "not_equals":
        return left != right
    if operator == "not_empty":
        return bool(left.strip())
    if operator == "empty":
        return not left.strip()
    if operator in {"greater_than", "less_than", "greater_or_equal", "less_or_equal"}:
        left_number = float(left or 0)
        right_number = float(right or 0)
        if operator == "greater_than":
            return left_number > right_number
        if operator == "less_than":
            return left_number < right_number
        if operator == "greater_or_equal":
            return left_number >= right_number
        return left_number <= right_number
    return right in left


def _extract_json_path(raw_value: str, path: str) -> Any:
    if not path:
        return raw_value
    value: Any = json.loads(raw_value)
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            value = value[int(part)]
        else:
            return None
    return value


def _resolve_model(provider: Optional[str], model: Optional[str]) -> Dict[str, Any]:
    if not provider:
        raise HTTPException(400, "请选择模型提供商或先添加供应商。")
    if not model:
        raise HTTPException(400, "请选择要调用的模型。")
    active = model_provider_service.get_active_provider_config(provider)
    if not active:
        raise HTTPException(400, f"Provider '{provider}' is not configured")
    credentials = active.get("credentials", {})
    return {
        "provider": provider,
        "model": model,
        "api_key": credentials.get("api_key"),
        "base_url": credentials.get("base_url"),
    }


def _validate_dsl(dsl: Dict[str, Any]) -> Dict[str, Any]:
    nodes = dsl.get("nodes") or []
    edges = dsl.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HTTPException(400, "Workflow DSL must contain nodes and edges arrays")
    node_ids = set()
    has_start = False
    has_terminal = False
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type")
        if not node_id:
            raise HTTPException(400, "Workflow node id is required")
        if node_id in node_ids:
            raise HTTPException(400, f"Duplicate workflow node id: {node_id}")
        if node_type not in NODE_TYPES:
            raise HTTPException(400, f"Unsupported workflow node type: {node_type}")
        if node_type == "start":
            has_start = True
        if node_type in TERMINAL_NODE_TYPES:
            has_terminal = True
        node_ids.add(node_id)
    if not has_start:
        raise HTTPException(400, "Workflow requires a start node")
    if not has_terminal:
        raise HTTPException(400, "Workflow requires an end or answer node")
    for edge in edges:
        if not edge.get("id"):
            raise HTTPException(400, "Workflow edge id is required")
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            raise HTTPException(400, "Workflow edge references missing node")
        label = edge.get("label")
        if label not in {None, "", "true", "false"}:
            raise HTTPException(400, "Workflow edge label must be true or false")
        source_handle = edge.get("sourceHandle")
        target_handle = edge.get("targetHandle")
        if source_handle is not None and not isinstance(source_handle, str):
            raise HTTPException(400, "Workflow edge sourceHandle must be a string")
        if target_handle is not None and not isinstance(target_handle, str):
            raise HTTPException(400, "Workflow edge targetHandle must be a string")
    validated = {
        "nodes": nodes,
        "edges": edges,
        "globals": dsl.get("globals") or {},
        "settings": dsl.get("settings") or {},
    }
    _topological_nodes(validated)
    _validate_condition_edges(validated)
    _validate_node_data(validated)
    return validated


def _validate_condition_edges(dsl: Dict[str, Any]) -> None:
    nodes = dsl.get("nodes") or []
    edges = dsl.get("edges") or []
    outgoing_by_source: Dict[str, List[Dict[str, Any]]] = {
        node["id"]: [] for node in nodes
    }
    for edge in edges:
        outgoing_by_source[edge["source"]].append(edge)

    for node in nodes:
        if node.get("type") in TERMINAL_NODE_TYPES and outgoing_by_source.get(
            node["id"]
        ):
            raise HTTPException(
                400, f"Terminal node '{node['id']}' cannot have outgoing edges"
            )

        if node.get("type") != "condition":
            continue
        outgoing = outgoing_by_source.get(node["id"], [])
        labels = {edge.get("label") for edge in outgoing}
        label_counts = {
            "true": sum(1 for edge in outgoing if edge.get("label") == "true"),
            "false": sum(1 for edge in outgoing if edge.get("label") == "false"),
        }
        if not outgoing:
            raise HTTPException(
                400, f"Condition node '{node['id']}' requires true/false outgoing edges"
            )
        if "true" not in labels or "false" not in labels:
            raise HTTPException(
                400,
                f"Condition node '{node['id']}' requires both true and false outgoing edges",
            )
        if label_counts["true"] != 1 or label_counts["false"] != 1:
            raise HTTPException(
                400,
                f"Condition node '{node['id']}' requires exactly one true edge and one false edge",
            )
        if any(edge.get("label") not in {"true", "false"} for edge in outgoing):
            raise HTTPException(
                400,
                f"Condition node '{node['id']}' outgoing edges must be labeled true or false",
            )
        if any(
            edge.get("sourceHandle") and edge.get("sourceHandle") != edge.get("label")
            for edge in outgoing
        ):
            raise HTTPException(
                400,
                f"Condition node '{node['id']}' source handles must match true/false labels",
            )


def _validate_node_data(dsl: Dict[str, Any]) -> None:
    for node in dsl.get("nodes") or []:
        data = _node_data(node)
        node_type = node.get("type")
        if node_type == "start":
            variables = data.get("variables", [])
            if variables and not isinstance(variables, list):
                raise HTTPException(400, "Start node variables must be an array")
            for variable in variables or []:
                if not isinstance(variable, dict) or not variable.get("key"):
                    raise HTTPException(400, "Start node variables require key")
        if node_type == "http":
            url = data.get("url")
            if not url:
                raise HTTPException(400, "HTTP node requires url")
            if data.get("method", "GET").upper() not in {"GET", "POST"}:
                raise HTTPException(400, "HTTP node method must be GET or POST")
        if node_type == "iteration" and not data.get("items"):
            raise HTTPException(400, "Iteration node requires items template")
        if node_type == "workflow" and not data.get("workflow_id"):
            raise HTTPException(400, "Workflow node requires workflow_id")
        if node_type == "merge" and not data.get("sources"):
            raise HTTPException(400, "Merge node requires sources")
        if node_type == "question_classifier" and not data.get("classes"):
            raise HTTPException(400, "Question classifier node requires classes")
        if node_type == "parameter_extractor" and not data.get("fields"):
            raise HTTPException(400, "Parameter extractor node requires fields")


def _apply_workflow_globals(dsl: Dict[str, Any], context: Dict[str, Any]) -> None:
    globals_map = dsl.get("globals") or {}
    if not isinstance(globals_map, dict):
        raise HTTPException(400, "Workflow globals must be an object")
    for key, value in globals_map.items():
        context.setdefault(key, value)


def _workflow_settings(dsl: Dict[str, Any]) -> Dict[str, Any]:
    settings = dsl.get("settings") or {}
    if not isinstance(settings, dict):
        raise HTTPException(400, "Workflow settings must be an object")
    return {
        "timeout": int(settings.get("timeout", WORKFLOW_LLM_TIMEOUT_SECONDS)),
        "parallelism": int(settings.get("parallelism", 4)),
        "on_error": settings.get("on_error", "stop"),
    }


def _build_adjacency(dsl: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Build adjacency list with edge labels for graph traversal."""
    nodes = dsl.get("nodes") or []
    edges = dsl.get("edges") or []
    adjacency: Dict[str, List[Dict[str, Any]]] = {node["id"]: [] for node in nodes}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        label = edge.get("label")  # Optional: "true", "false", or None
        adjacency[source].append({"target": target, "label": label})
    return adjacency


def _build_incoming(dsl: Dict[str, Any]) -> Dict[str, List[str]]:
    incoming: Dict[str, List[str]] = {node["id"]: [] for node in dsl.get("nodes") or []}
    for edge in dsl.get("edges") or []:
        incoming[edge["target"]].append(edge["source"])
    return incoming


def _find_start_nodes(dsl: Dict[str, Any]) -> List[str]:
    """Find all start node IDs in the workflow."""
    nodes = dsl.get("nodes") or []
    return [node["id"] for node in nodes if node.get("type") == "start"]


def _node_by_id(dsl: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in dsl.get("nodes") or []}


def _node_is_ready(
    node_id: str,
    nodes: Dict[str, Dict[str, Any]],
    incoming: Dict[str, List[str]],
    executed: Set[str],
    context: Dict[str, Any],
) -> bool:
    if node_id in executed:
        return False
    sources = incoming.get(node_id, [])
    if not all(source in executed for source in sources):
        return False
    node = nodes[node_id]
    if node.get("type") == "merge":
        merge_sources = _node_data(node).get("sources") or []
        return all(source_key in context for source_key in merge_sources)
    return True


def _frontier_nodes(
    dsl: Dict[str, Any],
    nodes: Dict[str, Dict[str, Any]],
    executed: Set[str],
    context: Dict[str, Any],
) -> List[str]:
    incoming = _build_incoming(dsl)
    return [
        node_id
        for node_id in nodes
        if _node_is_ready(node_id, nodes, incoming, executed, context)
    ]


def _terminal_output_from_traces(
    traces: List[Dict[str, Any]], nodes: Dict[str, Dict[str, Any]]
) -> Any:
    for trace in reversed(traces):
        node = nodes.get(trace["node_id"], {})
        if node.get("type") in TERMINAL_NODE_TYPES:
            return trace.get("output")
    return None


def _topological_nodes(dsl: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = dsl.get("nodes") or []
    edges = dsl.get("edges") or []
    node_by_id = {node["id"]: node for node in nodes}
    indegree = {node["id"]: 0 for node in nodes}
    outgoing: Dict[str, List[str]] = {node["id"]: [] for node in nodes}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        outgoing[source].append(target)
        indegree[target] += 1
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    ordered = []
    while queue:
        node_id = queue.pop(0)
        ordered.append(node_by_id[node_id])
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(ordered) != len(nodes):
        raise HTTPException(400, "Workflow graph cannot contain cycles")
    return ordered


async def _execute_node(
    node: Dict[str, Any],
    context: Dict[str, Any],
    payload: WorkflowRun,
) -> Dict[str, Any]:
    node_type = node.get("type")
    data = _node_data(node)
    started_at = datetime.utcnow().isoformat()
    output = None
    if node_type == "start":
        _apply_start_inputs(data, context)
        key = data.get("output_key", "input")
        output = context.get(key) or context.get("input") or context.get("prompt") or ""
        context[key] = output
    elif node_type == "template":
        output = _render_template(data.get("template"), context)
        context[data.get("output_key", "template_output")] = output
    elif node_type == "condition":
        output = _evaluate_condition(data, context)
        context[data.get("output_key", "condition_result")] = output
    elif node_type == "variable":
        assignments = data.get("assignments") or []
        if not isinstance(assignments, list):
            raise HTTPException(400, "Variable node assignments must be an array")
        output = {}
        for assignment in assignments:
            key = assignment.get("key")
            if not key:
                raise HTTPException(400, "Variable assignment key is required")
            value = _render_template(assignment.get("value"), context)
            context[key] = value
            output[key] = value
    elif node_type == "http":
        url = _resolve_secret(data.get("url"), context)
        method = str(data.get("method", "GET")).upper()
        body_template = data.get("body")
        request = urllib.request.Request(url, method=method)
        headers = data.get("headers") or {}
        for key, value in headers.items():
            request.add_header(str(key), _resolve_secret(value, context))
        auth_token = data.get("auth_token")
        if auth_token:
            request.add_header(
                "Authorization", f"Bearer {_resolve_secret(auth_token, context)}"
            )
        body = None
        if method == "POST":
            body = _render_template(body_template, context).encode("utf-8")
            request.add_header(
                "Content-Type", data.get("content_type", "application/json")
            )
        try:
            with urllib.request.urlopen(
                request, data=body, timeout=int(data.get("timeout", 15))
            ) as response:
                output = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            fallback = data.get("fallback")
            if fallback is not None:
                output = _render_template(fallback, context)
                context[data.get("output_key", "http_output")] = output
                return {
                    "node_id": node.get("id"),
                    "node_type": node_type,
                    "title": node.get("title") or data.get("title") or node_type,
                    "status": "fallback",
                    "input": dict(context),
                    "output": output,
                    "error": str(exc),
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat(),
                }
            raise HTTPException(502, f"HTTP node request failed: {exc}") from exc
        extracted = _extract_json_path(output, str(data.get("response_path") or ""))
        context[data.get("output_key", "http_output")] = extracted
        output = extracted
    elif node_type == "code":
        expression = data.get("expression")
        if not expression:
            raise HTTPException(400, "Code node requires expression")
        try:
            output = _safe_eval_expression(str(expression), context)
        except Exception as exc:
            raise HTTPException(400, f"Code node failed: {exc}") from exc
        context[data.get("output_key", "code_output")] = _json_safe(output)
    elif node_type == "iteration":
        raw_items = _render_template(data.get("items"), context)
        try:
            parsed_items = json.loads(raw_items)
        except json.JSONDecodeError:
            parsed_items = [
                item.strip() for item in raw_items.split(",") if item.strip()
            ]
        if not isinstance(parsed_items, list):
            raise HTTPException(400, "Iteration node items must resolve to an array")
        template = data.get("template", "{{item}}")
        if not parsed_items:
            context[data.get("output_key", "iteration_output")] = []
            output = []
        else:
            output = []
            subflow_id = data.get("workflow_id")
            for index, item in enumerate(parsed_items):
                child_context = dict(context)
                child_context["item"] = item
                child_context["index"] = index
                if subflow_id:
                    nested = _workflows.get(subflow_id)
                    if not nested:
                        raise HTTPException(
                            404, f"Nested workflow '{subflow_id}' not found"
                        )
                    nested_execution = await _execute_workflow_graph(
                        _validate_dsl(nested.get("dsl") or {}),
                        child_context,
                        WorkflowRun(inputs=child_context),
                    )
                    if nested_execution.get("status") != "succeeded":
                        raise HTTPException(
                            400,
                            f"Nested iteration workflow '{subflow_id}' failed",
                        )
                    output.append(nested_execution["final_output"])
                else:
                    output.append(_render_template(template, child_context))
            context[data.get("output_key", "iteration_output")] = output
    elif node_type == "workflow":
        workflow_id = data.get("workflow_id")
        nested = _workflows.get(workflow_id)
        if not nested:
            raise HTTPException(404, f"Nested workflow '{workflow_id}' not found")
        nested_context = dict(context)
        for key, value in (data.get("inputs") or {}).items():
            nested_context[key] = _render_template(value, context)
        nested_execution = await _execute_workflow_graph(
            _validate_dsl(nested.get("dsl") or {}),
            nested_context,
            WorkflowRun(inputs=nested_context),
        )
        output = nested_execution["final_output"]
        if data.get("result_path"):
            output = nested_context.get(str(data.get("result_path")), output)
        context[data.get("output_key", "workflow_output")] = output
    elif node_type == "merge":
        sources = data.get("sources") or []
        if not isinstance(sources, list):
            raise HTTPException(400, "Merge node sources must be an array")
        output = {source: context.get(source) for source in sources}
        context[data.get("output_key", "merge_output")] = output
    elif node_type == "tool":
        tool_name = str(data.get("tool", "template"))
        if tool_name == "template":
            output = _render_template(data.get("template"), context)
        else:
            output = json.dumps(
                {"tool": tool_name, "input": dict(context)}, ensure_ascii=False
            )
        context[data.get("output_key", "tool_output")] = output
    elif node_type == "question_classifier":
        text = _render_template(data.get("text") or context.get("input") or "", context)
        classes = data.get("classes") or ["general"]
        output = next(
            (label for label in classes if label and label in text),
            classes[0] if classes else "general",
        )
        context[data.get("output_key", "question_class")] = output
    elif node_type == "parameter_extractor":
        fields = data.get("fields") or []
        output = {}
        source = _render_template(
            data.get("text") or context.get("input") or "", context
        )
        for field in fields:
            key = field.get("key")
            if key:
                output[key] = source
                context[key] = source
        context[data.get("output_key", "parameters")] = output
    elif node_type == "list_operator":
        raw_items = context.get(data.get("list_key", "items"), [])
        items = raw_items if isinstance(raw_items, list) else []
        operation = data.get("operation", "join")
        if operation == "length":
            output = len(items)
        else:
            output = str(data.get("separator", ",")).join(str(item) for item in items)
        context[data.get("output_key", "list_output")] = output
    elif node_type == "document_extractor":
        source = _render_template(
            data.get("text") or context.get("input") or "", context
        )
        output = {"length": len(source), "preview": source[:200]}
        context[data.get("output_key", "document_output")] = output
    elif node_type == "approval":
        approval_key = data.get("approval_key", "approved")
        if approval_key not in context:
            now = datetime.utcnow().isoformat()
            return {
                "node_id": node.get("id"),
                "node_type": node_type,
                "title": node.get("title") or data.get("title") or node_type,
                "status": "paused",
                "input": dict(context),
                "output": None,
                "pause_key": approval_key,
                "started_at": started_at,
                "finished_at": now,
            }
        output = bool(context.get(approval_key))
        context[data.get("output_key", "approval_output")] = output
    elif node_type == "llm":
        provider = data.get("provider")
        model = data.get("model")
        if not provider:
            raise HTTPException(400, "LLM node requires 'provider' in node data")
        if not model:
            raise HTTPException(400, "LLM node requires 'model' in node data")
        resolved = _resolve_model(provider, model)
        prompt = _render_template(
            data.get("prompt") or context.get("prompt") or context.get("input") or "",
            context,
        )
        llm = LLMService(**resolved)
        completion = await asyncio.wait_for(
            llm.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                config=ChatConfig(
                    system_prompt=data.get("system_prompt")
                    or "你是工作流中的 LLM 节点。",
                    max_tokens=int(data.get("max_tokens", 1024)),
                    temperature=float(data.get("temperature", 0.7)),
                ),
            ),
            timeout=WORKFLOW_LLM_TIMEOUT_SECONDS,
        )
        output = completion.content
        context[data.get("output_key", "llm_output")] = output
    elif node_type == "knowledge":
        provider = data.get("provider")
        model = data.get("model")
        if not provider:
            raise HTTPException(400, "Knowledge node requires 'provider' in node data")
        if not model:
            raise HTTPException(400, "Knowledge node requires 'model' in node data")
        resolved = _resolve_model(provider, model)
        kb_id = data.get("knowledge_base_id")
        if not kb_id:
            raise HTTPException(400, "知识库节点需要选择知识库")
        rag = RAGService(
            config={
                "data_store_type": "sqlite",
                "llm_provider": resolved["provider"],
                "llm_model": resolved["model"],
                "api_key": resolved["api_key"],
                "base_url": resolved["base_url"],
            }
        )
        response = await rag.query(
            query=_render_template(
                data.get("query") or context.get("input") or "", context
            ),
            knowledge_base_id=kb_id,
            top_k=int(data.get("top_k", 5)),
        )
        output = response.answer
        context[data.get("output_key", "knowledge_output")] = output
    elif node_type == "end":
        output = _render_template(data.get("answer") or "{{llm_output}}", context)
        context[data.get("output_key", "answer")] = output
    elif node_type == "answer":
        output = _render_template(data.get("answer") or "{{answer}}", context)
        context[data.get("output_key", "answer")] = output
    return {
        "node_id": node.get("id"),
        "node_type": node_type,
        "title": node.get("title") or data.get("title") or node_type,
        "status": "succeeded",
        "input": dict(context),
        "output": output,
        "started_at": started_at,
        "finished_at": datetime.utcnow().isoformat(),
    }


def _next_edges_for_node(
    node: Dict[str, Any],
    trace: Dict[str, Any],
    outgoing_edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if node.get("type") != "condition":
        return outgoing_edges

    if not outgoing_edges:
        return []

    branch_label = "true" if bool(trace.get("output")) else "false"
    matched = [edge for edge in outgoing_edges if edge.get("label") == branch_label]
    if not matched:
        raise HTTPException(
            400,
            f"Condition node '{node.get('id')}' has no '{branch_label}' outgoing edge",
        )
    return matched


async def _execute_workflow_graph(
    dsl: Dict[str, Any],
    context: Dict[str, Any],
    payload: WorkflowRun,
    run_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _topological_nodes(dsl)
    _apply_workflow_globals(dsl, context)
    settings = _workflow_settings(dsl)
    nodes = _node_by_id(dsl)
    adjacency = _build_adjacency(dsl)
    incoming = _build_incoming(dsl)
    start_nodes = _find_start_nodes(dsl)
    if not start_nodes:
        raise HTTPException(400, "Workflow requires a start node")

    traces = list((run_record or {}).get("traces") or [])
    final_output = None
    executed: Set[str] = set((run_record or {}).get("executed_node_ids") or [])
    queue = _frontier_nodes(dsl, nodes, executed, context) or list(start_nodes)
    failed_node_id = None

    while queue:
        ready = []
        deferred = []
        for node_id in queue:
            if _node_is_ready(node_id, nodes, incoming, executed, context):
                ready.append(node_id)
            else:
                deferred.append(node_id)
        queue = deferred
        if not ready:
            break

        async def run_one(node_id: str) -> Dict[str, Any]:
            node = nodes[node_id]
            attempts = int(_node_data(node).get("retry", 0)) + 1
            last_error = None
            for attempt in range(1, attempts + 1):
                try:
                    trace = await _execute_node(node, context, payload)
                    trace["attempt"] = attempt
                    return trace
                except HTTPException as exc:
                    last_error = exc
                    if attempt >= attempts:
                        now = datetime.utcnow().isoformat()
                        return {
                            "node_id": node.get("id"),
                            "node_type": node.get("type"),
                            "title": node.get("title") or node.get("type"),
                            "status": "failed",
                            "input": dict(context),
                            "output": None,
                            "error": exc.detail,
                            "attempt": attempt,
                            "started_at": now,
                            "finished_at": now,
                        }
                    await asyncio.sleep(0)
            raise last_error or HTTPException(500, "Workflow node failed")

        batch = ready[: max(1, settings["parallelism"])]
        queue = ready[max(1, settings["parallelism"]) :] + queue
        batch_traces = await asyncio.wait_for(
            asyncio.gather(*(run_one(node_id) for node_id in batch)),
            timeout=max(1, settings["timeout"]),
        )
        for trace in batch_traces:
            traces.append(trace)
            current_node = nodes[trace["node_id"]]
            if trace["status"] in {"failed", "paused"}:
                failed_node_id = trace["node_id"]
                final_output = trace.get("output")
                if settings["on_error"] == "continue" and trace["status"] == "failed":
                    continue
                break
            executed.add(trace["node_id"])
            if current_node.get("type") in TERMINAL_NODE_TYPES:
                final_output = trace["output"]
            for edge in _next_edges_for_node(
                current_node, trace, adjacency.get(trace["node_id"], [])
            ):
                target = edge.get("target")
                if target and target not in executed and target not in queue:
                    queue.append(target)
        if failed_node_id:
            break
        if run_record is not None:
            run_record["context"] = context
            run_record["traces"] = traces
            run_record["executed_node_ids"] = list(executed)
            run_record["status"] = "running"
            run_record["updated_at"] = datetime.utcnow().isoformat()
            _persist_workflow_run_record(run_record)

    final_output = _terminal_output_from_traces(traces, nodes)

    return {
        "traces": traces,
        "final_output": final_output,
        "executed_node_ids": list(executed),
        "status": "failed" if failed_node_id else "succeeded",
        "paused": any(trace.get("status") == "paused" for trace in traces),
        "failed_node_id": failed_node_id,
    }


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
        "dsl": _default_dsl(),
    }
    _workflows[workflow_id] = workflow
    _persist_workflows()
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
    return _workflow_versions(workflow)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(get_current_user)):
    if workflow_id not in _workflows:
        raise HTTPException(404, "Workflow not found")
    del _workflows[workflow_id]
    _persist_workflows()
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
        _record_workflow_version(workflow)
        workflow["dsl"] = _validate_dsl(payload.dsl)
    _persist_workflows()
    return WorkflowOut(**workflow)


@router.get("/workflows/{workflow_id}/runs")
async def list_workflow_runs(workflow_id: str, user: dict = Depends(get_current_user)):
    if workflow_id not in _workflows:
        raise HTTPException(404, "Workflow not found")
    return _list_workflow_runs_for(workflow_id)


@router.get("/workflows/{workflow_id}/runs/{run_id}")
async def get_workflow_run(
    workflow_id: str, run_id: str, user: dict = Depends(get_current_user)
):
    run = _load_workflow_run(run_id)
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
    dsl = _validate_dsl(workflow.get("dsl") or {})
    context = dict(payload.inputs or {})
    run_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    run_record = {
        "id": run_id,
        "workflow_id": workflow_id,
        "status": "running",
        "inputs": payload.inputs or {},
        "context": context,
        "traces": [],
        "executed_node_ids": [],
        "result": None,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
    }
    _persist_workflow_run_record(run_record)
    try:
        execution = await _execute_workflow_graph(dsl, context, payload, run_record)
    except HTTPException:
        run_record["status"] = "failed"
        run_record["updated_at"] = datetime.utcnow().isoformat()
        run_record["finished_at"] = run_record["updated_at"]
        _persist_workflow_run_record(run_record)
        raise
    except Exception as exc:
        run_record["status"] = "failed"
        run_record["updated_at"] = datetime.utcnow().isoformat()
        run_record["finished_at"] = run_record["updated_at"]
        _persist_workflow_run_record(run_record)
        raise HTTPException(500, str(exc)) from exc
    run_record["status"] = "paused" if execution.get("paused") else execution["status"]
    run_record["context"] = context
    run_record["traces"] = execution["traces"]
    run_record["executed_node_ids"] = execution["executed_node_ids"]
    run_record["result"] = execution["final_output"]
    run_record["failed_node_id"] = execution["failed_node_id"]
    run_record["updated_at"] = datetime.utcnow().isoformat()
    run_record["finished_at"] = run_record["updated_at"]
    _persist_workflow_run_record(run_record)
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
            "context": context,
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
    dsl = _validate_dsl(workflow.get("dsl") or {})

    async def event_stream():
        result = await run_workflow(workflow_id, payload, user)
        output = result["output"]
        for trace in output.get("traces", []):
            yield f"data: {json.dumps({'type': 'trace', 'trace': trace}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'result', 'output': output}, ensure_ascii=False)}\n\n"

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
    run_record = _load_workflow_run(run_id)
    if not run_record or run_record.get("workflow_id") != workflow_id:
        raise HTTPException(404, "Workflow run not found")
    if run_record.get("status") == "succeeded":
        return run_record
    context = dict(run_record.get("context") or {})
    context.update(payload.inputs or {})
    if run_record.get("status") == "paused":
        paused_trace = next(
            (
                trace
                for trace in reversed(run_record.get("traces") or [])
                if trace.get("status") == "paused"
            ),
            None,
        )
        if paused_trace:
            paused_node_id = paused_trace.get("node_id")
            executed = set(run_record.get("executed_node_ids") or [])
            if paused_node_id:
                paused_node = _node_by_id(_validate_dsl(workflow.get("dsl") or {})).get(
                    paused_node_id
                )
                if paused_node and paused_node.get("type") == "approval":
                    paused_data = _node_data(paused_node)
                    approval_key = paused_data.get("approval_key", "approved")
                    context[paused_data.get("output_key", "approval_output")] = bool(
                        context.get(approval_key)
                    )
                executed.add(paused_node_id)
                run_record["executed_node_ids"] = list(executed)
            run_record["traces"] = [
                trace
                for trace in run_record.get("traces") or []
                if trace is not paused_trace
            ]
    run_record["status"] = "running"
    run_record["updated_at"] = datetime.utcnow().isoformat()
    _persist_workflow_run_record(run_record)
    execution = await _execute_workflow_graph(
        _validate_dsl(workflow.get("dsl") or {}),
        context,
        WorkflowRun(inputs=context),
        run_record,
    )
    run_record["status"] = "paused" if execution.get("paused") else execution["status"]
    run_record["context"] = context
    run_record["traces"] = execution["traces"]
    run_record["executed_node_ids"] = execution["executed_node_ids"]
    run_record["result"] = execution["final_output"]
    run_record["failed_node_id"] = execution["failed_node_id"]
    run_record["updated_at"] = datetime.utcnow().isoformat()
    run_record["finished_at"] = run_record["updated_at"]
    _persist_workflow_run_record(run_record)
    return run_record
