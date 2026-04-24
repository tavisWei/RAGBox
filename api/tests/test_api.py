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


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root():
    response = client.get("/")
    assert response.status_code == 200


def test_apps_list():
    response = client.get("/api/v1/apps", headers=auth_headers())
    assert response.status_code == 200
