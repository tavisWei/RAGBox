import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import app
from api.api import workflows as workflow_module


client = TestClient(app)


def auth_headers() -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_workflow_simulation_template_condition_end() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "simulation-test"},
        headers=headers,
    )
    assert created.status_code == 200
    workflow_id = created.json()["id"]

    dsl = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 80, "y": 120},
                "data": {"output_key": "input"},
            },
            {
                "id": "template",
                "type": "template",
                "title": "模板",
                "position": {"x": 320, "y": 120},
                "data": {"template": "输入是：{{input}}", "output_key": "prompt"},
            },
            {
                "id": "condition",
                "type": "condition",
                "title": "条件",
                "position": {"x": 560, "y": 120},
                "data": {
                    "left": "{{prompt}}",
                    "operator": "contains",
                    "right": "仿真",
                    "output_key": "condition_result",
                },
            },
            {
                "id": "end",
                "type": "end",
                "title": "结束",
                "position": {"x": 800, "y": 120},
                "data": {
                    "answer": "结果={{prompt}}; 条件={{condition_result}}",
                    "output_key": "answer",
                },
            },
            {
                "id": "false_end",
                "type": "end",
                "title": "未命中",
                "position": {"x": 800, "y": 280},
                "data": {"answer": "未命中", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-template", "source": "start", "target": "template"},
            {"id": "template-condition", "source": "template", "target": "condition"},
            {
                "id": "condition-end-true",
                "source": "condition",
                "target": "end",
                "sourceHandle": "true",
                "targetHandle": "target",
                "label": "true",
            },
            {
                "id": "condition-false_end-false",
                "source": "condition",
                "target": "false_end",
                "sourceHandle": "false",
                "targetHandle": "target",
                "label": "false",
            },
        ],
    }

    updated = client.put(
        f"/api/v1/workflows/{workflow_id}", json={"dsl": dsl}, headers=headers
    )
    assert updated.status_code == 200

    run = client.post(
        f"/api/v1/workflows/{workflow_id}/run",
        json={"inputs": {"input": "仿真流程测试"}},
        headers=headers,
    )
    assert run.status_code == 200
    output = run.json()["output"]
    assert output["result"] == "结果=输入是：仿真流程测试; 条件=True"
    assert output["context"]["condition_result"] is True
    assert len(output["traces"]) == 4
    assert [trace["node_id"] for trace in output["traces"]] == [
        "start",
        "template",
        "condition",
        "end",
    ]


def test_workflow_validation_requires_start_and_end() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "invalid-simulation-test"},
        headers=headers,
    )
    workflow_id = created.json()["id"]
    updated = client.put(
        f"/api/v1/workflows/{workflow_id}",
        json={"dsl": {"nodes": [], "edges": []}},
        headers=headers,
    )
    assert updated.status_code == 400
    assert "start" in updated.text


def test_workflow_condition_routes_only_matching_branch() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "branch-simulation-test"},
        headers=headers,
    )
    assert created.status_code == 200
    workflow_id = created.json()["id"]

    dsl = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 80, "y": 120},
                "data": {"output_key": "input"},
            },
            {
                "id": "condition",
                "type": "condition",
                "title": "条件",
                "position": {"x": 320, "y": 120},
                "data": {
                    "left": "{{input}}",
                    "operator": "contains",
                    "right": "通过",
                    "output_key": "condition_result",
                },
            },
            {
                "id": "true_end",
                "type": "end",
                "title": "通过分支",
                "position": {"x": 560, "y": 40},
                "data": {"answer": "走true: {{input}}", "output_key": "answer"},
            },
            {
                "id": "false_end",
                "type": "end",
                "title": "未通过分支",
                "position": {"x": 560, "y": 220},
                "data": {"answer": "走false: {{input}}", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-condition", "source": "start", "target": "condition"},
            {
                "id": "condition-true_end-true",
                "source": "condition",
                "target": "true_end",
                "sourceHandle": "true",
                "targetHandle": "target",
                "label": "true",
            },
            {
                "id": "condition-false_end-false",
                "source": "condition",
                "target": "false_end",
                "sourceHandle": "false",
                "targetHandle": "target",
                "label": "false",
            },
        ],
    }

    updated = client.put(
        f"/api/v1/workflows/{workflow_id}", json={"dsl": dsl}, headers=headers
    )
    assert updated.status_code == 200

    true_run = client.post(
        f"/api/v1/workflows/{workflow_id}/run",
        json={"inputs": {"input": "仿真通过"}},
        headers=headers,
    )
    assert true_run.status_code == 200
    true_output = true_run.json()["output"]
    assert true_output["result"] == "走true: 仿真通过"
    assert [trace["node_id"] for trace in true_output["traces"]] == [
        "start",
        "condition",
        "true_end",
    ]

    false_run = client.post(
        f"/api/v1/workflows/{workflow_id}/run",
        json={"inputs": {"input": "仿真失败"}},
        headers=headers,
    )
    assert false_run.status_code == 200
    false_output = false_run.json()["output"]
    assert false_output["result"] == "走false: 仿真失败"
    assert [trace["node_id"] for trace in false_output["traces"]] == [
        "start",
        "condition",
        "false_end",
    ]


def test_workflow_validation_rejects_duplicate_nodes_bad_edges_and_cycles() -> None:
    duplicate = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "start", "type": "end", "data": {}},
        ],
        "edges": [],
    }
    with pytest.raises(HTTPException):
        workflow_module._validate_dsl(duplicate)

    bad_edge = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "end", "type": "end", "data": {}},
        ],
        "edges": [{"id": "missing", "source": "start", "target": "missing"}],
    }
    with pytest.raises(HTTPException):
        workflow_module._validate_dsl(bad_edge)

    cyclic = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "middle", "type": "template", "data": {"template": "x"}},
            {"id": "end", "type": "end", "data": {}},
        ],
        "edges": [
            {"id": "start-middle", "source": "start", "target": "middle"},
            {"id": "middle-start", "source": "middle", "target": "start"},
            {"id": "middle-end", "source": "middle", "target": "end"},
        ],
    }
    with pytest.raises(HTTPException):
        workflow_module._validate_dsl(cyclic)


def test_workflow_validation_rejects_incomplete_condition_edges() -> None:
    missing_false = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "condition", "type": "condition", "data": {}},
            {"id": "end", "type": "end", "data": {}},
            {"id": "false_end", "type": "end", "data": {}},
        ],
        "edges": [
            {"id": "start-condition", "source": "start", "target": "condition"},
            {
                "id": "condition-end-true",
                "source": "condition",
                "target": "end",
                "sourceHandle": "true",
                "label": "true",
            },
        ],
    }
    with pytest.raises(HTTPException) as missing_false_error:
        workflow_module._validate_dsl(missing_false)
    assert "both true and false" in str(missing_false_error.value.detail)

    unlabeled_condition_edge = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "condition", "type": "condition", "data": {}},
            {"id": "end", "type": "end", "data": {}},
            {"id": "false_end", "type": "end", "data": {}},
        ],
        "edges": [
            {"id": "start-condition", "source": "start", "target": "condition"},
            {"id": "condition-end", "source": "condition", "target": "end"},
            {
                "id": "condition-false_end-false",
                "source": "condition",
                "target": "false_end",
                "sourceHandle": "false",
                "label": "false",
            },
        ],
    }
    with pytest.raises(HTTPException) as unlabeled_error:
        workflow_module._validate_dsl(unlabeled_condition_edge)
    assert "both true and false" in str(unlabeled_error.value.detail)

    mismatched_handle = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "condition", "type": "condition", "data": {}},
            {"id": "end", "type": "end", "data": {}},
            {"id": "false_end", "type": "end", "data": {}},
        ],
        "edges": [
            {"id": "start-condition", "source": "start", "target": "condition"},
            {
                "id": "condition-end-true",
                "source": "condition",
                "target": "end",
                "sourceHandle": "false",
                "label": "true",
            },
            {
                "id": "condition-false_end-false",
                "source": "condition",
                "target": "false_end",
                "sourceHandle": "false",
                "label": "false",
            },
        ],
    }
    with pytest.raises(HTTPException) as mismatched_error:
        workflow_module._validate_dsl(mismatched_handle)
    assert "source handles" in str(mismatched_error.value.detail)

    duplicate_true = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "condition", "type": "condition", "data": {}},
            {"id": "end", "type": "end", "data": {}},
            {"id": "end2", "type": "end", "data": {}},
            {"id": "false_end", "type": "end", "data": {}},
        ],
        "edges": [
            {"id": "start-condition", "source": "start", "target": "condition"},
            {
                "id": "condition-end-true",
                "source": "condition",
                "target": "end",
                "sourceHandle": "true",
                "label": "true",
            },
            {
                "id": "condition-end2-true",
                "source": "condition",
                "target": "end2",
                "sourceHandle": "true",
                "label": "true",
            },
            {
                "id": "condition-false_end-false",
                "source": "condition",
                "target": "false_end",
                "sourceHandle": "false",
                "label": "false",
            },
        ],
    }
    with pytest.raises(HTTPException) as duplicate_error:
        workflow_module._validate_dsl(duplicate_true)
    assert "exactly one true" in str(duplicate_error.value.detail)


def test_workflow_validation_rejects_end_node_outgoing_edge() -> None:
    end_outgoing = {
        "nodes": [
            {"id": "start", "type": "start", "data": {}},
            {"id": "end", "type": "end", "data": {}},
            {"id": "template", "type": "template", "data": {"template": "x"}},
        ],
        "edges": [
            {"id": "start-end", "source": "start", "target": "end"},
            {"id": "end-template", "source": "end", "target": "template"},
        ],
    }
    with pytest.raises(HTTPException) as error:
        workflow_module._validate_dsl(end_outgoing)
    assert "cannot have outgoing" in str(error.value.detail)


def test_llm_node_does_not_fallback_to_run_payload_model(monkeypatch) -> None:
    def fake_resolve_model(provider: str, model: str) -> dict:
        if provider or model:
            raise AssertionError("LLM node used run payload provider/model fallback")
        raise HTTPException(400, "请选择模型提供商或先添加供应商。")

    monkeypatch.setattr(workflow_module, "_resolve_model", fake_resolve_model)
    node = {
        "id": "llm",
        "type": "llm",
        "title": "LLM",
        "data": {"prompt": "{{input}}", "output_key": "llm_output"},
    }
    payload = workflow_module.WorkflowRun(
        inputs={"input": "hello"}, provider="payload-provider", model="payload-model"
    )

    with pytest.raises(HTTPException):
        asyncio.run(workflow_module._execute_node(node, {"input": "hello"}, payload))


def test_llm_node_executes_with_explicit_node_model(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_module,
        "_resolve_model",
        lambda provider, model: {
            "provider": provider,
            "model": model,
            "api_key": "test-key",
            "base_url": "http://example.test",
        },
    )

    class FakeCompletion:
        content = "fake llm answer"

    class FakeLLMService:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def chat(self, messages, config):
            assert self.kwargs["provider"] == "minimax"
            assert self.kwargs["model"] == "abab6.5"
            assert messages[0].content == "Say hi to Ada"
            return FakeCompletion()

    monkeypatch.setattr(workflow_module, "LLMService", FakeLLMService)
    node = {
        "id": "llm",
        "type": "llm",
        "title": "LLM",
        "data": {
            "provider": "minimax",
            "model": "abab6.5",
            "prompt": "Say hi to {{name}}",
            "output_key": "llm_output",
        },
    }
    context = {"name": "Ada"}
    trace = asyncio.run(
        workflow_module._execute_node(
            node, context, workflow_module.WorkflowRun(inputs={})
        )
    )
    assert trace["output"] == "fake llm answer"
    assert context["llm_output"] == "fake llm answer"


def test_knowledge_node_executes_with_explicit_node_model(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_module,
        "_resolve_model",
        lambda provider, model: {
            "provider": provider,
            "model": model,
            "api_key": "test-key",
            "base_url": "http://example.test",
        },
    )

    class FakeRagResponse:
        answer = "fake knowledge answer"

    class FakeRAGService:
        def __init__(self, config):
            assert config["llm_provider"] == "minimax"
            assert config["llm_model"] == "abab6.5"

        async def query(self, query, knowledge_base_id, top_k):
            assert query == "Find Ada"
            assert knowledge_base_id == "kb-1"
            assert top_k == 3
            return FakeRagResponse()

    monkeypatch.setattr(workflow_module, "RAGService", FakeRAGService)
    node = {
        "id": "knowledge",
        "type": "knowledge",
        "title": "知识库",
        "data": {
            "provider": "minimax",
            "model": "abab6.5",
            "knowledge_base_id": "kb-1",
            "query": "Find {{name}}",
            "top_k": 3,
            "output_key": "knowledge_output",
        },
    }
    context = {"name": "Ada"}
    trace = asyncio.run(
        workflow_module._execute_node(
            node, context, workflow_module.WorkflowRun(inputs={})
        )
    )
    assert trace["output"] == "fake knowledge answer"
    assert context["knowledge_output"] == "fake knowledge answer"


def test_workflow_delete_api() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "delete-test"},
        headers=headers,
    )
    assert created.status_code == 200
    workflow_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/workflows/{workflow_id}", headers=headers)
    assert deleted.status_code == 200

    missing = client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
    assert missing.status_code == 404


def test_workflow_run_history_versions_and_resume() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "history-test"},
        headers=headers,
    )
    workflow_id = created.json()["id"]
    dsl = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 0, "y": 0},
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "type": "string", "required": True}],
                },
            },
            {
                "id": "variable",
                "type": "variable",
                "title": "变量",
                "position": {"x": 200, "y": 0},
                "data": {"assignments": [{"key": "name", "value": "{{input}}"}]},
            },
            {
                "id": "code",
                "type": "code",
                "title": "代码",
                "position": {"x": 400, "y": 0},
                "data": {
                    "expression": "context.get('name', '').upper()",
                    "output_key": "code_output",
                },
            },
            {
                "id": "iteration",
                "type": "iteration",
                "title": "迭代",
                "position": {"x": 600, "y": 0},
                "data": {
                    "items": '["a", "b"]',
                    "template": "item={{item}}",
                    "output_key": "items_output",
                },
            },
            {
                "id": "end",
                "type": "end",
                "title": "结束",
                "position": {"x": 800, "y": 0},
                "data": {
                    "answer": "{{code_output}} / {{items_output}}",
                    "output_key": "answer",
                },
            },
        ],
        "edges": [
            {"id": "start-variable", "source": "start", "target": "variable"},
            {"id": "variable-code", "source": "variable", "target": "code"},
            {"id": "code-iteration", "source": "code", "target": "iteration"},
            {"id": "iteration-end", "source": "iteration", "target": "end"},
        ],
    }
    updated = client.put(
        f"/api/v1/workflows/{workflow_id}", json={"dsl": dsl}, headers=headers
    )
    assert updated.status_code == 200
    versions = client.get(f"/api/v1/workflows/{workflow_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()) >= 1

    run = client.post(
        f"/api/v1/workflows/{workflow_id}/run",
        json={"inputs": {"input": "ada"}},
        headers=headers,
    )
    assert run.status_code == 200
    output = run.json()["output"]
    assert output["status"] == "succeeded"
    assert output["result"] == "ADA / ['item=a', 'item=b']"
    run_id = output["run_id"]

    runs = client.get(f"/api/v1/workflows/{workflow_id}/runs", headers=headers)
    assert runs.status_code == 200
    assert any(item["id"] == run_id for item in runs.json())
    detail = client.get(
        f"/api/v1/workflows/{workflow_id}/runs/{run_id}", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["result"] == output["result"]
    resumed = client.post(
        f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume",
        json={"inputs": {}},
        headers=headers,
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "succeeded"


def test_condition_node_supports_richer_operators() -> None:
    context = {"left": "5", "empty_value": ""}
    greater = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "condition",
                "type": "condition",
                "data": {"left": "{{left}}", "operator": "greater_than", "right": "3"},
            },
            dict(context),
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    empty = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "condition-empty",
                "type": "condition",
                "data": {"left": "{{empty_value}}", "operator": "empty", "right": ""},
            },
            dict(context),
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    assert greater["output"] is True
    assert empty["output"] is True


def test_http_node_extracts_json_path_and_auth(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"data":{"answer":"ok"}}'

    def fake_urlopen(request, data=None, timeout=0):
        assert request.headers["Authorization"] == "Bearer token-123"
        return FakeResponse()

    monkeypatch.setattr(workflow_module.urllib.request, "urlopen", fake_urlopen)
    context = {"token": "token-123"}
    trace = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "http",
                "type": "http",
                "data": {
                    "url": "https://example.com",
                    "method": "GET",
                    "auth_token": "{{token}}",
                    "response_path": "data.answer",
                    "output_key": "http_output",
                },
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    assert trace["output"] == "ok"
    assert context["http_output"] == "ok"


def test_iteration_node_handles_empty_array() -> None:
    context = {}
    trace = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "iteration",
                "type": "iteration",
                "data": {"items": "[]", "template": "{{item}}", "output_key": "items"},
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    assert trace["output"] == []
    assert context["items"] == []


def test_workflow_node_executes_nested_workflow() -> None:
    nested_id = "nested-workflow-test"
    workflow_module._workflows[nested_id] = {
        "id": nested_id,
        "app_id": "qa-app",
        "name": "nested",
        "dsl": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "title": "开始",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "output_key": "input",
                        "variables": [{"key": "input", "required": True}],
                    },
                },
                {
                    "id": "end",
                    "type": "end",
                    "title": "结束",
                    "position": {"x": 100, "y": 0},
                    "data": {"answer": "nested={{input}}", "output_key": "answer"},
                },
            ],
            "edges": [{"id": "start-end", "source": "start", "target": "end"}],
            "globals": {},
        },
    }
    context = {"input": "Ada"}
    trace = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "workflow",
                "type": "workflow",
                "data": {"workflow_id": nested_id, "output_key": "nested_output"},
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    assert trace["output"] == "nested=Ada"
    assert context["nested_output"] == "nested=Ada"


def test_execute_workflow_graph_retries_failed_node(monkeypatch) -> None:
    attempts = {"count": 0}

    async def fake_execute_node(node, context, payload):
        if node["id"] == "template":
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise HTTPException(400, "temporary failure")
        return {
            "node_id": node["id"],
            "node_type": node["type"],
            "title": node.get("title") or node["type"],
            "status": "succeeded",
            "input": dict(context),
            "output": node["id"],
            "started_at": "now",
            "finished_at": "now",
        }

    monkeypatch.setattr(workflow_module, "_execute_node", fake_execute_node)
    dsl = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
                "title": "开始",
            },
            {
                "id": "template",
                "type": "template",
                "data": {"retry": 1},
                "title": "模板",
            },
            {"id": "end", "type": "end", "data": {}, "title": "结束"},
        ],
        "edges": [
            {"id": "start-template", "source": "start", "target": "template"},
            {"id": "template-end", "source": "template", "target": "end"},
        ],
        "globals": {},
    }
    result = asyncio.run(
        workflow_module._execute_workflow_graph(
            dsl,
            {"input": "ok"},
            workflow_module.WorkflowRun(inputs={"input": "ok"}),
        )
    )
    assert attempts["count"] == 2
    assert result["status"] == "succeeded"


def test_workflow_simulation_http_code_iteration_merge_answer(monkeypatch) -> None:
    headers = auth_headers()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"data":{"name":"Ada"}}'

    monkeypatch.setattr(
        workflow_module.urllib.request,
        "urlopen",
        lambda request, data=None, timeout=0: FakeResponse(),
    )

    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "http-code-iteration-merge-answer"},
        headers=headers,
    )
    workflow_id = created.json()["id"]
    dsl = {
        "globals": {"apiToken": "token"},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 0, "y": 0},
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "http",
                "type": "http",
                "title": "HTTP",
                "position": {"x": 180, "y": 0},
                "data": {
                    "url": "https://example.com",
                    "method": "GET",
                    "auth_token": "{{apiToken}}",
                    "response_path": "data.name",
                    "output_key": "http_name",
                },
            },
            {
                "id": "code",
                "type": "code",
                "title": "代码",
                "position": {"x": 360, "y": 0},
                "data": {
                    "expression": "context.get('http_name', '').upper()",
                    "output_key": "upper_name",
                },
            },
            {
                "id": "iteration",
                "type": "iteration",
                "title": "迭代",
                "position": {"x": 540, "y": 0},
                "data": {
                    "items": '["x","y"]',
                    "template": "{{item}}",
                    "output_key": "iterated",
                },
            },
            {
                "id": "merge",
                "type": "merge",
                "title": "合并",
                "position": {"x": 720, "y": 0},
                "data": {"sources": ["upper_name", "iterated"], "output_key": "merged"},
            },
            {
                "id": "answer",
                "type": "answer",
                "title": "回答",
                "position": {"x": 900, "y": 0},
                "data": {
                    "answer": "{{upper_name}} / {{iterated}}",
                    "output_key": "answer",
                },
            },
        ],
        "edges": [
            {"id": "start-http", "source": "start", "target": "http"},
            {"id": "http-code", "source": "http", "target": "code"},
            {"id": "code-iteration", "source": "code", "target": "iteration"},
            {"id": "iteration-merge", "source": "iteration", "target": "merge"},
            {"id": "merge-answer", "source": "merge", "target": "answer"},
        ],
    }
    client.put(f"/api/v1/workflows/{workflow_id}", json={"dsl": dsl}, headers=headers)
    run = client.post(
        f"/api/v1/workflows/{workflow_id}/run",
        json={"inputs": {"input": "ignored"}},
        headers=headers,
    )
    assert run.status_code == 200
    output = run.json()["output"]
    assert output["status"] == "succeeded"
    assert output["result"] == "ADA / ['x', 'y']"


def test_workflow_simulation_subworkflow_and_approval_pause_resume() -> None:
    headers = auth_headers()
    nested = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "nested-child"},
        headers=headers,
    )
    nested_id = nested.json()["id"]
    nested_dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 0, "y": 0},
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "end",
                "type": "end",
                "title": "结束",
                "position": {"x": 100, "y": 0},
                "data": {"answer": "nested={{input}}", "output_key": "answer"},
            },
        ],
        "edges": [{"id": "start-end", "source": "start", "target": "end"}],
    }
    client.put(
        f"/api/v1/workflows/{nested_id}", json={"dsl": nested_dsl}, headers=headers
    )

    parent = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "approval-parent"},
        headers=headers,
    )
    parent_id = parent.json()["id"]
    parent_dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "position": {"x": 0, "y": 0},
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "workflow",
                "type": "workflow",
                "title": "子工作流",
                "position": {"x": 200, "y": 0},
                "data": {
                    "workflow_id": nested_id,
                    "inputs": {"input": "{{input}}"},
                    "output_key": "nested_output",
                },
            },
            {
                "id": "approval",
                "type": "approval",
                "title": "审批",
                "position": {"x": 400, "y": 0},
                "data": {"approval_key": "approved", "output_key": "approval_output"},
            },
            {
                "id": "end",
                "type": "end",
                "title": "结束",
                "position": {"x": 600, "y": 0},
                "data": {
                    "answer": "{{nested_output}} / {{approval_output}}",
                    "output_key": "answer",
                },
            },
        ],
        "edges": [
            {"id": "start-workflow", "source": "start", "target": "workflow"},
            {"id": "workflow-approval", "source": "workflow", "target": "approval"},
            {"id": "approval-end", "source": "approval", "target": "end"},
        ],
    }
    client.put(
        f"/api/v1/workflows/{parent_id}", json={"dsl": parent_dsl}, headers=headers
    )
    first_run = client.post(
        f"/api/v1/workflows/{parent_id}/run",
        json={"inputs": {"input": "Ada"}},
        headers=headers,
    )
    assert first_run.status_code == 200
    paused = first_run.json()["output"]
    assert paused["status"] == "paused"
    run_id = paused["run_id"]
    resumed = client.post(
        f"/api/v1/workflows/{parent_id}/runs/{run_id}/resume",
        json={"inputs": {"approved": True}},
        headers=headers,
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "succeeded"
    assert resumed.json()["result"] == "nested=Ada / True"


def test_code_node_blocks_unsafe_attribute_access() -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            workflow_module._execute_node(
                {
                    "id": "code",
                    "type": "code",
                    "data": {
                        "expression": "context.__class__",
                        "output_key": "code_output",
                    },
                },
                {"input": "x"},
                workflow_module.WorkflowRun(inputs={}),
            )
        )
    assert "not allowed" in str(error.value.detail)


def test_extra_dify_like_nodes_execute() -> None:
    context = {"input": "billing question", "items": ["a", "b"]}
    classifier = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "classifier",
                "type": "question_classifier",
                "data": {
                    "text": "{{input}}",
                    "classes": ["billing", "general"],
                    "output_key": "question_class",
                },
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    extractor = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "extractor",
                "type": "parameter_extractor",
                "data": {
                    "text": "{{input}}",
                    "fields": [{"key": "query"}],
                    "output_key": "params",
                },
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    list_op = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "list",
                "type": "list_operator",
                "data": {
                    "list_key": "items",
                    "operation": "join",
                    "separator": "|",
                    "output_key": "joined",
                },
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    doc = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "doc",
                "type": "document_extractor",
                "data": {"text": "{{input}}", "output_key": "doc_output"},
            },
            context,
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    assert classifier["output"] == "billing"
    assert extractor["output"]["query"] == "billing question"
    assert list_op["output"] == "a|b"
    assert doc["output"]["length"] == len("billing question")


def test_http_node_post_body_and_headers(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok":true}'

    captured = {}

    def fake_urlopen(request, data=None, timeout=0):
        captured["method"] = request.get_method()
        captured["content_type"] = request.get_header(
            "Content-type"
        ) or request.get_header("Content-Type")
        captured["body"] = data.decode("utf-8") if data else None
        return FakeResponse()

    monkeypatch.setattr(workflow_module.urllib.request, "urlopen", fake_urlopen)
    trace = asyncio.run(
        workflow_module._execute_node(
            {
                "id": "http",
                "type": "http",
                "data": {
                    "url": "https://example.com",
                    "method": "POST",
                    "body": '{"name":"{{input}}"}',
                    "content_type": "application/json",
                    "output_key": "http_output",
                },
            },
            {"input": "Ada"},
            workflow_module.WorkflowRun(inputs={}),
        )
    )
    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/json"
    assert captured["body"] == '{"name":"Ada"}'
    assert trace["output"] == '{"ok":true}'


def test_merge_node_waits_for_parallel_sources() -> None:
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "title": "开始",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "left",
                "type": "template",
                "title": "左",
                "data": {"template": "L", "output_key": "left_out"},
            },
            {
                "id": "right",
                "type": "template",
                "title": "右",
                "data": {"template": "R", "output_key": "right_out"},
            },
            {
                "id": "merge",
                "type": "merge",
                "title": "合并",
                "data": {"sources": ["left_out", "right_out"], "output_key": "merged"},
            },
            {
                "id": "end",
                "type": "end",
                "title": "结束",
                "data": {"answer": "{{merged}}", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-left", "source": "start", "target": "left"},
            {"id": "start-right", "source": "start", "target": "right"},
            {"id": "left-merge", "source": "left", "target": "merge"},
            {"id": "right-merge", "source": "right", "target": "merge"},
            {"id": "merge-end", "source": "merge", "target": "end"},
        ],
    }
    result = asyncio.run(
        workflow_module._execute_workflow_graph(
            workflow_module._validate_dsl(dsl),
            {"input": "x"},
            workflow_module.WorkflowRun(inputs={"input": "x"}),
        )
    )
    assert result["final_output"] == "{'left_out': 'L', 'right_out': 'R'}"


def test_iteration_nested_workflow_failure_bubbles() -> None:
    workflow_module._workflows["bad-nested"] = {
        "id": "bad-nested",
        "app_id": "qa-app",
        "name": "bad nested",
        "dsl": {
            "globals": {},
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "data": {
                        "output_key": "input",
                        "variables": [{"key": "input", "required": True}],
                    },
                },
                {
                    "id": "code",
                    "type": "code",
                    "data": {"expression": "context.__class__", "output_key": "boom"},
                },
                {"id": "end", "type": "end", "data": {"answer": "{{boom}}"}},
            ],
            "edges": [
                {"id": "start-code", "source": "start", "target": "code"},
                {"id": "code-end", "source": "code", "target": "end"},
            ],
        },
    }
    result = asyncio.run(
        workflow_module._execute_workflow_graph(
            workflow_module._validate_dsl(
                {
                    "globals": {},
                    "nodes": [
                        {
                            "id": "start",
                            "type": "start",
                            "data": {
                                "output_key": "input",
                                "variables": [{"key": "input", "required": True}],
                            },
                        },
                        {
                            "id": "iteration",
                            "type": "iteration",
                            "data": {
                                "items": '["a"]',
                                "workflow_id": "bad-nested",
                                "output_key": "items",
                            },
                        },
                        {"id": "end", "type": "end", "data": {"answer": "{{items}}"}},
                    ],
                    "edges": [
                        {
                            "id": "start-iteration",
                            "source": "start",
                            "target": "iteration",
                        },
                        {"id": "iteration-end", "source": "iteration", "target": "end"},
                    ],
                }
            ),
            {"input": "x"},
            workflow_module.WorkflowRun(inputs={"input": "x"}),
        )
    )
    assert result["status"] == "failed"


def test_multiple_approval_resume_flow() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "multi-approval"},
        headers=headers,
    )
    workflow_id = created.json()["id"]
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "approval1",
                "type": "approval",
                "data": {"approval_key": "approved1", "output_key": "a1"},
            },
            {
                "id": "approval2",
                "type": "approval",
                "data": {"approval_key": "approved2", "output_key": "a2"},
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "{{a1}}/{{a2}}", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-a1", "source": "start", "target": "approval1"},
            {"id": "a1-a2", "source": "approval1", "target": "approval2"},
            {"id": "a2-end", "source": "approval2", "target": "end"},
        ],
    }
    client.put(f"/api/v1/workflows/{workflow_id}", json={"dsl": dsl}, headers=headers)
    first = client.post(
        f"/api/v1/workflows/{workflow_id}/run",
        json={"inputs": {"input": "x"}},
        headers=headers,
    )
    run_id = first.json()["output"]["run_id"]
    first_resume = client.post(
        f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume",
        json={"inputs": {"approved1": True}},
        headers=headers,
    )
    assert first_resume.json()["status"] == "paused"
    second_resume = client.post(
        f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume",
        json={"inputs": {"approved2": True}},
        headers=headers,
    )
    assert second_resume.json()["status"] == "succeeded"
    assert second_resume.json()["result"] == "True/True"


def test_workflow_on_error_continue_skips_failed_node() -> None:
    dsl = {
        "globals": {},
        "settings": {"timeout": 60, "parallelism": 4, "on_error": "continue"},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "broken",
                "type": "code",
                "data": {"expression": "context.__class__", "output_key": "broken"},
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "done", "output_key": "answer"},
            },
        ],
        "edges": [
            {"id": "start-broken", "source": "start", "target": "broken"},
            {"id": "broken-end", "source": "broken", "target": "end"},
        ],
    }
    result = asyncio.run(
        workflow_module._execute_workflow_graph(
            workflow_module._validate_dsl(dsl),
            {"input": "x"},
            workflow_module.WorkflowRun(inputs={"input": "x"}),
        )
    )
    assert result["status"] == "failed"
    assert any(trace["status"] == "failed" for trace in result["traces"])


def test_workflow_globals_injection() -> None:
    dsl = {
        "globals": {"greeting": "hello"},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "{{greeting}} {{input}}", "output_key": "answer"},
            },
        ],
        "edges": [{"id": "start-end", "source": "start", "target": "end"}],
    }
    result = asyncio.run(
        workflow_module._execute_workflow_graph(
            workflow_module._validate_dsl(dsl),
            {"input": "world"},
            workflow_module.WorkflowRun(inputs={"input": "world"}),
        )
    )
    assert result["final_output"] == "hello world"


def test_stream_endpoint_emits_trace_and_result_events() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/workflows",
        json={"app_id": "qa-app", "name": "stream-test"},
        headers=headers,
    )
    workflow_id = created.json()["id"]
    dsl = {
        "globals": {},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "output_key": "input",
                    "variables": [{"key": "input", "required": True}],
                },
            },
            {
                "id": "end",
                "type": "end",
                "data": {"answer": "{{input}}", "output_key": "answer"},
            },
        ],
        "edges": [{"id": "start-end", "source": "start", "target": "end"}],
    }
    client.put(f"/api/v1/workflows/{workflow_id}", json={"dsl": dsl}, headers=headers)
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/run/stream",
        json={"inputs": {"input": "stream"}},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.text
    assert '"type": "trace"' in body or '"type":"trace"' in body
    assert '"type": "result"' in body or '"type":"result"' in body
