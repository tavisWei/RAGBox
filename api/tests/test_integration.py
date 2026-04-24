import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def auth_headers() -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAppsEndpoints:
    def test_list_apps(self):
        response = client.get("/api/v1/apps", headers=auth_headers())
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_app(self):
        response = client.post(
            "/api/v1/apps",
            json={"name": "Test App", "mode": "chat"},
            headers=auth_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test App"
        assert "id" in data

    def test_get_app(self):
        create_response = client.post(
            "/api/v1/apps",
            json={"name": "Get Test", "mode": "chat"},
            headers=auth_headers(),
        )
        app_id = create_response.json()["id"]
        response = client.get(f"/api/v1/apps/{app_id}", headers=auth_headers())
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test"


class TestAgentEndpoints:
    def test_run_agent(self):
        response = client.post(
            "/api/v1/agent/run", json={"query": "Hello"}, headers=auth_headers()
        )
        assert response.status_code == 400
        assert (
            "请选择模型提供商" in response.text or "请选择要调用的模型" in response.text
        )


class TestMemoryEndpoints:
    def test_add_memory(self):
        response = client.post(
            "/api/v1/memory/test-conv/add",
            json={"role": "user", "content": "Hello"},
            headers=auth_headers(),
        )
        assert response.status_code == 200

    def test_get_memory(self):
        client.post(
            "/api/v1/memory/test-conv-2/add",
            json={"role": "user", "content": "Hello"},
            headers=auth_headers(),
        )
        response = client.get("/api/v1/memory/test-conv-2", headers=auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data


class TestPromptEndpoints:
    def test_format_prompt(self):
        response = client.post(
            "/api/v1/prompt/format",
            json={"template": "Hello {{name}}", "inputs": {"name": "World"}},
            headers=auth_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "Hello World"


class TestKnowledgeBaseEndpoints:
    def test_list_knowledge_bases(self):
        response = client.get("/api/v1/knowledge-bases", headers=auth_headers())
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestRetrievalEndpoints:
    def test_get_config_presets(self):
        response = client.get("/api/v1/retrieval/config-presets")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert data[0]["name"] == "beginner"


class TestAuthEndpoints:
    def test_login(self):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_register(self):
        email = f"integration-{uuid4().hex[:8]}@example.com"
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "test"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
