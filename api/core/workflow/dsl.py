"""Workflow DSL schema, defaults and validation.

Moved verbatim from api/api/workflows.py; this is the contract shared with
the frontend workflow editor, so semantics must not change here.
"""

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

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


def default_dsl() -> Dict[str, Any]:
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


def node_data(node: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(node.get("data") or {})
    for key, value in node.items():
        if key not in {"id", "type", "title", "position", "data"}:
            data.setdefault(key, value)
    return data


def validate_dsl(dsl: Dict[str, Any]) -> Dict[str, Any]:
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
    topological_nodes(validated)
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
        data = node_data(node)
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


def apply_workflow_globals(dsl: Dict[str, Any], context: Dict[str, Any]) -> None:
    globals_map = dsl.get("globals") or {}
    if not isinstance(globals_map, dict):
        raise HTTPException(400, "Workflow globals must be an object")
    for key, value in globals_map.items():
        context.setdefault(key, value)


def workflow_settings(dsl: Dict[str, Any]) -> Dict[str, Any]:
    settings = dsl.get("settings") or {}
    if not isinstance(settings, dict):
        raise HTTPException(400, "Workflow settings must be an object")
    return {
        "timeout": int(settings.get("timeout", WORKFLOW_LLM_TIMEOUT_SECONDS)),
        "parallelism": int(settings.get("parallelism", 4)),
        "on_error": settings.get("on_error", "stop"),
    }


def node_by_id(dsl: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in dsl.get("nodes") or []}


def terminal_output_from_traces(
    traces: List[Dict[str, Any]], nodes: Dict[str, Dict[str, Any]]
) -> Any:
    for trace in reversed(traces):
        node = nodes.get(trace["node_id"], {})
        if node.get("type") in TERMINAL_NODE_TYPES:
            return trace.get("output")
    return None


def topological_nodes(dsl: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = dsl.get("nodes") or []
    edges = dsl.get("edges") or []
    node_map = {node["id"]: node for node in nodes}
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
        ordered.append(node_map[node_id])
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(ordered) != len(nodes):
        raise HTTPException(400, "Workflow graph cannot contain cycles")
    return ordered
