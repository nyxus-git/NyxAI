"""
api/tests/test_chat.py

Tests for POST /chat endpoint.

These tests verify:
  - Basic chat request/response cycle
  - Conversation ID handling (new vs continuing)
  - Input validation (empty message, too long, etc.)
  - Multilingual message support
  - Error handling when Ollama is unavailable
  - Response schema correctness
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from api.tests.conftest import MockLLMProvider
from core.brain.llm import LLMConnectionError, LLMModelError, LLMTimeoutError


class TestChatEndpoint:
    """Test suite for POST /chat."""

    # ── Basic functionality ────────────────────────────────────────────────────

    def test_chat_returns_200(self, test_client: TestClient) -> None:
        """A valid chat request should return HTTP 200."""
        response = test_client.post("/chat", json={"message": "Hello NyxAI!"})
        assert response.status_code == 200

    def test_chat_response_schema(self, test_client: TestClient) -> None:
        """Response should contain response, conversation_id, and model fields."""
        response = test_client.post("/chat", json={"message": "Hello!"})
        data = response.json()

        assert "response" in data
        assert "conversation_id" in data
        assert "model" in data

        assert isinstance(data["response"], str)
        assert isinstance(data["model"], str)

    def test_chat_response_is_not_empty(self, test_client: TestClient) -> None:
        """NyxAI's response should never be an empty string."""
        response = test_client.post("/chat", json={"message": "Hey!"})
        data = response.json()

        assert data["response"]
        assert len(data["response"]) > 0

    def test_chat_returns_valid_conversation_id(self, test_client: TestClient) -> None:
        """A new conversation should return a valid UUID."""
        response = test_client.post("/chat", json={"message": "Hello!"})
        data = response.json()

        # Should be parseable as a UUID
        conv_id = uuid.UUID(data["conversation_id"])
        assert isinstance(conv_id, uuid.UUID)

    def test_chat_new_conversation_gets_unique_id(self, test_client: TestClient) -> None:
        """Two separate new conversations should get different IDs."""
        r1 = test_client.post("/chat", json={"message": "Message 1"})
        r2 = test_client.post("/chat", json={"message": "Message 2"})

        id1 = r1.json()["conversation_id"]
        id2 = r2.json()["conversation_id"]

        assert id1 != id2

    # ── Conversation continuity ────────────────────────────────────────────────

    def test_chat_continues_conversation_with_same_id(
        self, test_client: TestClient, sample_conversation_id: uuid.UUID
    ) -> None:
        """Providing a conversation_id should return the SAME conversation_id."""
        conv_id_str = str(sample_conversation_id)

        response = test_client.post(
            "/chat",
            json={"message": "Tell me more.", "conversation_id": conv_id_str},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id_str

    def test_chat_model_name_in_response(self, test_client: TestClient) -> None:
        """Response should include the model name that generated the reply."""
        response = test_client.post("/chat", json={"message": "Hello!"})
        data = response.json()

        assert data["model"] == "test-model"  # Matches MockLLMProvider default

    # ── Multilingual support ───────────────────────────────────────────────────

    def test_chat_accepts_hindi_message(self, test_client: TestClient) -> None:
        """Hindi messages should be accepted without validation errors."""
        response = test_client.post("/chat", json={"message": "नमस्ते! तुम्ही कसे आहात?"})
        assert response.status_code == 200

    def test_chat_accepts_marathi_message(self, test_client: TestClient) -> None:
        """Marathi messages should be accepted without validation errors."""
        response = test_client.post("/chat", json={"message": "आज काय plan आहे?"})
        assert response.status_code == 200

    def test_chat_accepts_hinglish_message(self, test_client: TestClient) -> None:
        """Hinglish (mixed Hindi-English) messages should be accepted."""
        response = test_client.post(
            "/chat", json={"message": "Hey Nyx! आज VS Code उघड आणि project open कर."}
        )
        assert response.status_code == 200

    # ── Input validation ──────────────────────────────────────────────────────

    def test_chat_rejects_empty_message(self, test_client: TestClient) -> None:
        """An empty message should return HTTP 422 (validation error)."""
        response = test_client.post("/chat", json={"message": ""})
        assert response.status_code == 422

    def test_chat_rejects_missing_message_field(self, test_client: TestClient) -> None:
        """A request with no 'message' field should return HTTP 422."""
        response = test_client.post("/chat", json={})
        assert response.status_code == 422

    def test_chat_rejects_invalid_conversation_id(self, test_client: TestClient) -> None:
        """An invalid UUID in conversation_id should return HTTP 422."""
        response = test_client.post(
            "/chat",
            json={"message": "Hello!", "conversation_id": "not-a-valid-uuid"},
        )
        assert response.status_code == 422

    def test_chat_accepts_null_conversation_id(self, test_client: TestClient) -> None:
        """conversation_id=null should be accepted (starts new conversation)."""
        response = test_client.post(
            "/chat", json={"message": "Hello!", "conversation_id": None}
        )
        assert response.status_code == 200

    # ── LLM error handling ────────────────────────────────────────────────────

    def test_chat_returns_503_when_ollama_connection_error(
        self, test_client: TestClient, mock_llm: MockLLMProvider
    ) -> None:
        """LLMConnectionError from the provider should return HTTP 503."""

        async def raise_connection_error(*args, **kwargs):
            raise LLMConnectionError("Cannot connect to Ollama.")

        mock_llm.chat = raise_connection_error  # type: ignore[method-assign]

        response = test_client.post("/chat", json={"message": "Hello!"})
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["error"] == "llm_unavailable"

    def test_chat_returns_503_when_model_not_found(
        self, test_client: TestClient, mock_llm: MockLLMProvider
    ) -> None:
        """LLMModelError should return HTTP 503 with model_unavailable error."""

        async def raise_model_error(*args, **kwargs):
            raise LLMModelError("Model 'qwen2.5:3b' not found.")

        mock_llm.chat = raise_model_error  # type: ignore[method-assign]

        response = test_client.post("/chat", json={"message": "Hello!"})
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["error"] == "model_unavailable"

    def test_chat_returns_504_when_llm_timeout(
        self, test_client: TestClient, mock_llm: MockLLMProvider
    ) -> None:
        """LLMTimeoutError should return HTTP 504."""

        async def raise_timeout(*args, **kwargs):
            raise LLMTimeoutError("Request timed out.")

        mock_llm.chat = raise_timeout  # type: ignore[method-assign]

        response = test_client.post("/chat", json={"message": "Hello!"})
        assert response.status_code == 504
        data = response.json()
        assert data["detail"]["error"] == "llm_timeout"
