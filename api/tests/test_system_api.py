"""
api/tests/test_system_api.py

Unit tests for GET /system/telemetry and POST /system/quick-action.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.routers.system import router as system_router
from core.agent.tool_registry import build_default_registry


@pytest.fixture
def system_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(system_router)
    app.state.tool_registry = build_default_registry()
    return TestClient(app)


def test_get_telemetry_endpoint(system_test_client: TestClient) -> None:
    response = system_test_client.get("/system/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert "cpu" in data
    assert "ram" in data
    assert "battery" in data
    assert "gpu" in data
    assert "uptime" in data
    assert "agents" in data

    assert isinstance(data["agents"], list)
    assert len(data["agents"]) >= 5
    agent_ids = [a["id"] for a in data["agents"]]
    assert "supervisor" in agent_ids
    assert "routine_agent" in agent_ids
    assert "media_agent" in agent_ids
    assert "terminal_agent" in agent_ids


def test_quick_action_activate_all_tasks(system_test_client: TestClient) -> None:
    response = system_test_client.post(
        "/system/quick-action",
        json={"action": "activate_all_tasks", "params": {}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "activate_all_tasks"
    assert "data" in data
    assert "hardware" in data["data"]


def test_quick_action_media_control(system_test_client: TestClient) -> None:
    response = system_test_client.post(
        "/system/quick-action",
        json={"action": "control_media", "params": {"action": "play_pause"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "control_media"


def test_quick_action_terminal_sandboxed(system_test_client: TestClient) -> None:
    response = system_test_client.post(
        "/system/quick-action",
        json={"action": "run_terminal", "params": {"command": "echo 'JARVIS ONLINE'"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "JARVIS ONLINE" in data["data"]["stdout"]


def test_quick_action_unsupported_action(system_test_client: TestClient) -> None:
    response = system_test_client.post(
        "/system/quick-action",
        json={"action": "self_destruct_now", "params": {}},
    )
    assert response.status_code == 400

