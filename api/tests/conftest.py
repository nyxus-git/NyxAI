"""
api/tests/conftest.py

Pytest fixtures shared across all NyxAI API tests.

Key design decisions:
  - Tests use a mock LLM provider so they never require Ollama to be running.
  - The lifespan is bypassed in tests by using `app.router.lifespan_context`
    override — we inject mock state directly into app.state so the real
    startup logic (which calls Ollama) is never triggered.
  - This makes tests fast, deterministic, and runnable in CI without GPU/Ollama.
"""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.config import get_settings
from api.app.services.chat_service import ChatService
from core.brain.llm import LLMProvider, LLMResponse, Message


# ─── Mock LLM Provider ────────────────────────────────────────────────────────


class MockLLMProvider(LLMProvider):
    """
    A deterministic mock LLM provider for testing.

    Returns predictable responses without calling Ollama.
    Tracks call counts and last-received messages for assertions.
    """

    def __init__(
        self,
        model: str = "test-model",
        response_text: str = "नमस्ते! मी NyxAI आहे. मी तुम्हाला कसे मदत करू?",
        healthy: bool = True,
    ) -> None:
        self.model = model
        self.response_text = response_text
        self.healthy = healthy
        self.chat_call_count = 0
        self.last_messages: list[Message] = []

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.chat_call_count += 1
        self.last_messages = messages
        return LLMResponse(
            content=self.response_text,
            model=self.model,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content=self.response_text,
            model=self.model,
            prompt_tokens=5,
            completion_tokens=15,
            total_tokens=20,
        )

    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        for word in self.response_text.split():
            yield word + " "

    async def health_check(self) -> bool:
        return self.healthy

    def get_model_name(self) -> str:
        return self.model

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        temperature: float = 0.5,
    ):
        """Mock chat_with_tools — returns a text response with no tool calls."""
        from core.brain.llm import LLMResponseWithTools
        self.chat_call_count += 1
        self.last_messages = messages
        return LLMResponseWithTools(
            content=self.response_text,
            model=self.model,
            tool_calls=[],
            prompt_tokens=10,
            completion_tokens=20,
        )


# ─── Test App Factory ─────────────────────────────────────────────────────────


def make_test_app(mock_provider: MockLLMProvider) -> FastAPI:
    """
    Create a FastAPI test app with a mock lifespan that injects the
    mock LLM provider instead of running real startup logic.

    This bypasses Ollama entirely so tests run without a running LLM.
    """
    from api.app.routers import chat, health
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def mock_lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Inject mock services into app.state — no real Ollama calls."""
        app.state.settings = get_settings()
        app.state.llm_provider = mock_provider
        app.state.chat_service = ChatService(llm_provider=mock_provider, agent=None)
        app.state.agent = None
        app.state.tool_registry = None
        yield
        # No cleanup needed for mock

    app = FastAPI(title="NyxAI Test", version="0.1.0", lifespan=mock_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    return app


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    """Return a healthy mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_unhealthy() -> MockLLMProvider:
    """Return an unhealthy mock LLM provider (Ollama down simulation)."""
    return MockLLMProvider(healthy=False)


@pytest.fixture
def test_client(mock_llm: MockLLMProvider) -> TestClient:
    """
    Create a FastAPI TestClient with the mock LLM injected via a mock lifespan.
    The real startup (which calls Ollama) is completely bypassed.
    """
    app = make_test_app(mock_llm)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture
def test_client_unhealthy(mock_llm_unhealthy: MockLLMProvider) -> TestClient:
    """
    TestClient where Ollama is simulated as unreachable.
    Used to test graceful degradation behavior.
    """
    app = make_test_app(mock_llm_unhealthy)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture
def sample_conversation_id() -> uuid.UUID:
    """Return a fixed UUID for conversation continuity tests."""
    return uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
