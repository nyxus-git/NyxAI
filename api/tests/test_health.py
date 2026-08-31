"""
api/tests/test_health.py

Tests for GET /health endpoint.

These tests verify:
  - The endpoint returns HTTP 200
  - The response schema is correct
  - The status reflects Ollama connectivity (healthy vs degraded)
  - All required fields are present
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test suite for GET /health."""

    def test_health_returns_200(self, test_client: TestClient) -> None:
        """Health endpoint should always return HTTP 200."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_response_schema(self, test_client: TestClient) -> None:
        """Response should contain all required fields with correct types."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "model" in data
        assert "ollama_connected" in data

        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["model"], str)
        assert isinstance(data["ollama_connected"], bool)

    def test_health_status_healthy_when_ollama_up(self, test_client: TestClient) -> None:
        """Status should be 'healthy' when Ollama mock returns True."""
        response = test_client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["ollama_connected"] is True

    def test_health_status_degraded_when_ollama_down(
        self, test_client_unhealthy: TestClient
    ) -> None:
        """Status should be 'degraded' (not error) when Ollama is unreachable."""
        response = test_client_unhealthy.get("/health")

        # The endpoint should still return 200 — the service is alive,
        # just degraded. It should never crash because Ollama is down.
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["ollama_connected"] is False

    def test_health_model_name_present(self, test_client: TestClient) -> None:
        """Model name should be present in response (never empty)."""
        response = test_client.get("/health")
        data = response.json()

        assert data["model"]  # Non-empty string
        assert len(data["model"]) > 0

    def test_health_version_present(self, test_client: TestClient) -> None:
        """Version should be a non-empty string."""
        response = test_client.get("/health")
        data = response.json()

        assert data["version"]
        assert len(data["version"]) > 0
