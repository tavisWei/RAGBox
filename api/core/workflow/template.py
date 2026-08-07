"""Template rendering, expression sandbox and input casting for workflow nodes.

Moved verbatim from api/api/workflows.py. These functions are part of the DSL
contract with the frontend editor (`{{var}}` interpolation, `{{secret:ENV}}`,
whitelist eval), so semantics must not change here.
"""

import ast
import json
import os
import re
from typing import Any, Dict, Optional

from fastapi import HTTPException


def render_template(template: Any, context: Dict[str, Any]) -> str:
    output = str(template or "")
    for key, value in context.items():
        output = output.replace("{{" + key + "}}", str(value))
    return output


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def cast_input_value(value: Any, value_type: Optional[str]) -> Any:
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


def resolve_secret(template: Any, context: Dict[str, Any]) -> str:
    rendered = render_template(template, context)

    def replacer(match: re.Match) -> str:
        return os.getenv(match.group(1), "")

    return re.sub(r"\{\{secret:([A-Z0-9_]+)\}\}", replacer, rendered)


def safe_eval_expression(expression: str, context: Dict[str, Any]) -> Any:
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


def apply_start_inputs(data: Dict[str, Any], context: Dict[str, Any]) -> None:
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
            context[key] = cast_input_value(variable.get("default"), variable.get("type"))
        if variable.get("required") and key not in context:
            raise HTTPException(400, f"Missing required workflow input: {key}")
        if key in context:
            context[key] = cast_input_value(context[key], variable.get("type"))


def evaluate_condition(data: Dict[str, Any], context: Dict[str, Any]) -> bool:
    left = render_template(data.get("left"), context)
    operator = data.get("operator", "contains")
    right = render_template(data.get("right"), context)
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


def extract_json_path(raw_value: str, path: str) -> Any:
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
