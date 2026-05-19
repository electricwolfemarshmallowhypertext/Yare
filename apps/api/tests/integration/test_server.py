import os
import pytest
from fastapi.testclient import TestClient

from src.memory.server import create_app

API_KEY = "integration-key"
API_KEYS = f"{API_KEY}:admin|*"


@pytest.fixture(scope="session", autouse=True)
def _env():
    os.environ["ENV"] = "test"
    os.environ["LOG_LEVEL"] = "ERROR"
    os.environ["API_KEYS"] = API_KEYS
    os.environ["SQLITE_PATH"] = "data/test/fallback.db"
    os.environ["REDIS_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    yield


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def auth_headers():
    return {"Authorization": f"Bearer {API_KEY}"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()


def test_store_and_get_memory(client):
    mem = {
        "id": "inttest1",
        "text": "Hello",
        "type": "fact",
        "salience": 0.5,
        "created_at": "2025-01-01T00:00:00Z",
        "thread_id": "t",
        "user_id": "u",
        "persona_id": "p",
    }
    r1 = client.post("/memories", json=mem, headers=auth_headers())
    assert r1.status_code in (200, 201)
    r2 = client.get("/memories/inttest1", headers=auth_headers())
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == "inttest1"


def test_orchestration(client):
    wf = {
        "nodes": [
            {"id": "plan", "agent": "planner", "input": {"goal": "article"}},
            {"id": "write", "agent": "writer", "input": {"text": "Hello", "style": "concise"}, "depends_on": ["plan"]},
            {"id": "analyze", "agent": "analyst", "depends_on": ["write"]},
        ],
        "shared": {"project_id": "projX"},
    }
    r = client.post("/orchestrations", json=wf, headers=auth_headers())
    assert r.status_code == 200
    wid = r.json()["workflow_id"]

    # poll a few times for completion
    for _ in range(10):
        st = client.get(f"/orchestrations/{wid}", headers=auth_headers())
        assert st.status_code == 200
        if st.json()["status"] in ("completed", "failed", "canceled"):
            break