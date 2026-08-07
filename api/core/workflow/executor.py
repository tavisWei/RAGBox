"""Per-node executors for every workflow DSL node type.

Moved from api/api/workflows.py. The LLM branch calls LangChain chat models
(api.core.workflow.llm) and the tool branch invokes LangChain tools
(api.core.workflow.tools); knowledge nodes keep using the in-house RAGService.
"""

import asyncio
import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage

from api.core.workflow.dsl import WORKFLOW_LLM_TIMEOUT_SECONDS, node_data
from api.core.workflow.llm import build_chat_model
from api.core.workflow.template import (
    apply_start_inputs,
    evaluate_condition,
    extract_json_path,
    json_safe,
    render_template,
    resolve_secret,
    safe_eval_expression,
)
from api.core.workflow.tools import TOOL_REGISTRY
from api.services import workflow_store
from api.services.llm_service import (
    ChatConfig,
    ChatMessage,
    LLMService,
    build_model_identity_system_prompt,
)
from api.services.model_provider_service import model_provider_service
from api.services.rag_service import RAGService


def resolve_model(provider: Optional[str], model: Optional[str]) -> Dict[str, Any]:
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


async def _run_subflow(
    workflow_id: str, child_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a nested workflow through the LangGraph runner.

    Lazy import: executor -> runner -> compiler -> nodes -> executor is a
    genuine recursion cycle (workflows may contain workflow nodes), so the
    import stays inside the function.
    """
    from api.core.workflow import runner

    nested = workflow_store._workflows.get(workflow_id)
    if not nested:
        raise HTTPException(404, f"Nested workflow '{workflow_id}' not found")
    return await runner.execute(
        nested.get("dsl") or {}, child_context, run_id=str(uuid4())
    )


async def execute_node(
    node: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    node_type = node.get("type")
    data = node_data(node)
    started_at = datetime.utcnow().isoformat()
    output = None
    if node_type == "start":
        apply_start_inputs(data, context)
        key = data.get("output_key", "input")
        output = context.get(key) or context.get("input") or context.get("prompt") or ""
        context[key] = output
    elif node_type == "template":
        output = render_template(data.get("template"), context)
        context[data.get("output_key", "template_output")] = output
    elif node_type == "condition":
        output = evaluate_condition(data, context)
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
            value = render_template(assignment.get("value"), context)
            context[key] = value
            output[key] = value
    elif node_type == "http":
        url = resolve_secret(data.get("url"), context)
        method = str(data.get("method", "GET")).upper()
        body_template = data.get("body")
        request = urllib.request.Request(url, method=method)
        headers = data.get("headers") or {}
        for key, value in headers.items():
            request.add_header(str(key), resolve_secret(value, context))
        auth_token = data.get("auth_token")
        if auth_token:
            request.add_header(
                "Authorization", f"Bearer {resolve_secret(auth_token, context)}"
            )
        body = None
        if method == "POST":
            body = render_template(body_template, context).encode("utf-8")
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
                output = render_template(fallback, context)
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
        extracted = extract_json_path(output, str(data.get("response_path") or ""))
        context[data.get("output_key", "http_output")] = extracted
        output = extracted
    elif node_type == "code":
        expression = data.get("expression")
        if not expression:
            raise HTTPException(400, "Code node requires expression")
        try:
            output = safe_eval_expression(str(expression), context)
        except Exception as exc:
            raise HTTPException(400, f"Code node failed: {exc}") from exc
        context[data.get("output_key", "code_output")] = json_safe(output)
    elif node_type == "iteration":
        raw_items = render_template(data.get("items"), context)
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
                    nested_execution = await _run_subflow(subflow_id, child_context)
                    if nested_execution.get("status") != "succeeded":
                        raise HTTPException(
                            400,
                            f"Nested iteration workflow '{subflow_id}' failed",
                        )
                    output.append(nested_execution["final_output"])
                else:
                    output.append(render_template(template, child_context))
            context[data.get("output_key", "iteration_output")] = output
    elif node_type == "workflow":
        workflow_id = data.get("workflow_id")
        nested_context = dict(context)
        for key, value in (data.get("inputs") or {}).items():
            nested_context[key] = render_template(value, context)
        nested_execution = await _run_subflow(workflow_id, nested_context)
        output = nested_execution["final_output"]
        if data.get("result_path"):
            output = nested_execution.get("context", nested_context).get(
                str(data.get("result_path")), output
            )
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
            output = render_template(data.get("template"), context)
        else:
            tool_obj = TOOL_REGISTRY.get(tool_name)
            if tool_obj is None:
                raise HTTPException(
                    400,
                    f"Unknown tool '{tool_name}'. "
                    f"Available tools: {sorted(TOOL_REGISTRY)}",
                )
            raw_input = render_template(
                data.get("template") or data.get("input") or "", context
            )
            arg_names = list(tool_obj.args.keys())
            if len(arg_names) == 1:
                tool_input: Any = {arg_names[0]: raw_input}
            else:
                tool_input = json.loads(raw_input) if raw_input.strip() else {}
            output = str(await tool_obj.ainvoke(tool_input))
        context[data.get("output_key", "tool_output")] = output
    elif node_type == "question_classifier":
        text = render_template(data.get("text") or context.get("input") or "", context)
        classes = data.get("classes") or ["general"]
        output = next(
            (label for label in classes if label and label in text),
            classes[0] if classes else "general",
        )
        context[data.get("output_key", "question_class")] = output
    elif node_type == "parameter_extractor":
        fields = data.get("fields") or []
        output = {}
        source = render_template(
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
        source = render_template(
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
        resolved = resolve_model(provider, model)
        prompt = render_template(
            data.get("prompt") or context.get("prompt") or context.get("input") or "",
            context,
        )
        base_system_prompt = data.get("system_prompt") or "你是工作流中的 LLM 节点。"
        if str(resolved["provider"]).lower() == "demo":
            # Demo provider keeps the canned-response path from LLMService.
            llm = LLMService(**resolved)
            completion = await asyncio.wait_for(
                llm.chat(
                    messages=[ChatMessage(role="user", content=prompt)],
                    config=ChatConfig(
                        system_prompt=base_system_prompt,
                        max_tokens=int(data.get("max_tokens", 1024)),
                        temperature=float(data.get("temperature", 0.7)),
                    ),
                ),
                timeout=WORKFLOW_LLM_TIMEOUT_SECONDS,
            )
            output = completion.content
        else:
            system_prompt = build_model_identity_system_prompt(
                base_system_prompt, resolved["provider"], resolved["model"]
            )
            chat_model = build_chat_model(
                resolved,
                max_tokens=int(data.get("max_tokens", 1024)),
                temperature=float(data.get("temperature", 0.7)),
                timeout=WORKFLOW_LLM_TIMEOUT_SECONDS,
            )
            response = await chat_model.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt),
                ]
            )
            output = (
                response.content
                if isinstance(response.content, str)
                else json.dumps(response.content, ensure_ascii=False)
            )
        context[data.get("output_key", "llm_output")] = output
    elif node_type == "knowledge":
        provider = data.get("provider")
        model = data.get("model")
        if not provider:
            raise HTTPException(400, "Knowledge node requires 'provider' in node data")
        if not model:
            raise HTTPException(400, "Knowledge node requires 'model' in node data")
        resolved = resolve_model(provider, model)
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
            query=render_template(
                data.get("query") or context.get("input") or "", context
            ),
            knowledge_base_id=kb_id,
            top_k=int(data.get("top_k", 5)),
        )
        output = response.answer
        context[data.get("output_key", "knowledge_output")] = output
    elif node_type == "end":
        output = render_template(data.get("answer") or "{{llm_output}}", context)
        context[data.get("output_key", "answer")] = output
    elif node_type == "answer":
        output = render_template(data.get("answer") or "{{answer}}", context)
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
