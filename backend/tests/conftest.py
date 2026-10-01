import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVOLVE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("EVOLVE_SECURE_COOKIES", "false")
    with TestClient(app, headers={"X-Evolve-Request": "1"}) as c:
        yield c


@pytest.fixture
def account(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test Learner",
            "email": "learner@example.com",
            "password": "a-long-test-password",
        },
    )
    assert response.status_code == 201
    return client
