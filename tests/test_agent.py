"""
tests/test_agent.py

Unit tests for NyxAgent (core/agent/agent.py).

Tests:
  - Agent direct text response (no tools needed)
  - Agent single tool invocation and response generation
  - Agent unknown tool error handling
  - Agent confirmation required handling (e.g. open_application)
  - Agent max iterations loop prevention
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent.agent import NyxAgent
from core.agent.schemas import AgentResponse, ToolCall, ToolDefinition, ToolParameter, ToolResult
from core.agent.tool_registry import ToolRegistry
from core.brain.llm import LLMProvider, LLMResponse, LLMResponseWithTools


@pytest.fixture
def mock_llm() -> MagicMock:
    """Fixture providing a mocked LLMProvider."""
    llm = MagicMock(spec=LLMProvider)
    llm.get_model_name.return_value = "test-qwen-model"
    llm.chat = AsyncMock(
        return_value=LLMResponse(
            content="Synthesized final response from available data.",
            model="test-qwen-model",
        )
    )
    return llm


@pytest.fixture
def sample_tool_registry() -> ToolRegistry:
    """Fixture providing a ToolRegistry with sample tools."""
    registry = ToolRegistry()

    def dummy_battery() -> ToolResult:
        return ToolResult(
            tool_name="get_battery_status",
            success=True,
            data={"percentage": 85, "plugged_in": False},
        )

    battery_def = ToolDefinition(
        name="get_battery_status",
        description="Get current battery status.",
        parameters={},
    )
    registry.register(definition=battery_def, handler=dummy_battery)
    return registry


@pytest.mark.asyncio
async def test_agent_direct_response(mock_llm: MagicMock, sample_tool_registry: ToolRegistry):
    """When LLM returns direct text without tool calls, agent returns it immediately."""
    mock_llm.chat_with_tools = AsyncMock(
        return_value=LLMResponseWithTools(
            content="Hello! I am NyxAI.",
            model="test-qwen-model",
            tool_calls=[],
        )
    )

    agent = NyxAgent(llm_provider=mock_llm, tool_registry=sample_tool_registry, max_iterations=3)
    response: AgentResponse = await agent.run("Hello NyxAI")

    assert response.content == "Hello! I am NyxAI."
    assert response.model == "test-qwen-model"
    assert response.tool_used is None
    assert response.iterations == 1
    mock_llm.chat_with_tools.assert_called_once()


@pytest.mark.asyncio
async def test_agent_executes_tool_successfully(mock_llm: MagicMock, sample_tool_registry: ToolRegistry):
    """When LLM calls a registered tool, agent executes it and queries LLM with the result."""
    mock_llm.chat_with_tools = AsyncMock(
        side_effect=[
            LLMResponseWithTools(
                content="",
                model="test-qwen-model",
                tool_calls=[ToolCall(name="get_battery_status", arguments={})],
            ),
            LLMResponseWithTools(
                content="Your battery is at 85%.",
                model="test-qwen-model",
                tool_calls=[],
            ),
        ]
    )

    agent = NyxAgent(llm_provider=mock_llm, tool_registry=sample_tool_registry, max_iterations=3)
    response = await agent.run("What's my battery?")

    assert response.content == "Your battery is at 85%."
    assert response.tool_used == "get_battery_status"
    assert response.tool_result == {"percentage": 85, "plugged_in": False}
    assert response.iterations == 2
    assert mock_llm.chat_with_tools.call_count == 2


@pytest.mark.asyncio
async def test_agent_handles_unknown_tool(mock_llm: MagicMock, sample_tool_registry: ToolRegistry):
    """When LLM calls an unregistered tool, agent catches error and feeds back to LLM."""
    mock_llm.chat_with_tools = AsyncMock(
        side_effect=[
            LLMResponseWithTools(
                content="",
                model="test-qwen-model",
                tool_calls=[ToolCall(name="non_existent_tool", arguments={})],
            ),
            LLMResponseWithTools(
                content="Sorry, I could not execute that operation.",
                model="test-qwen-model",
                tool_calls=[],
            ),
        ]
    )

    agent = NyxAgent(llm_provider=mock_llm, tool_registry=sample_tool_registry, max_iterations=3)
    response = await agent.run("Do something invalid")

    assert response.content == "Sorry, I could not execute that operation."
    assert response.tool_used == "non_existent_tool"
    assert response.iterations == 2


@pytest.mark.asyncio
async def test_agent_handles_confirmation_required(mock_llm: MagicMock):
    """When a tool requires confirmation (Level 2), agent intercepts and returns pending confirmation message."""
    registry = ToolRegistry()

    def dummy_app(application: str) -> ToolResult:
        return ToolResult(tool_name="open_application", success=True, data={"launched": application})

    app_def = ToolDefinition(
        name="open_application",
        description="Open an app.",
        parameters={"application": ToolParameter(type="string", description="App name", required=True)},
    )
    registry.register(definition=app_def, handler=dummy_app)

    mock_llm.chat_with_tools = AsyncMock(
        return_value=LLMResponseWithTools(
            content="",
            model="test-qwen-model",
            tool_calls=[ToolCall(name="open_application", arguments={"application": "firefox"})],
        )
    )

    agent = NyxAgent(llm_provider=mock_llm, tool_registry=registry, max_iterations=3)
    response = await agent.run("Open Firefox")

    assert "need your confirmation first" in response.content
    assert response.tool_used == "open_application"
    assert response.tool_result == {"status": "pending_confirmation"}
    assert response.iterations == 1


@pytest.mark.asyncio
async def test_agent_max_iterations_prevention(mock_llm: MagicMock, sample_tool_registry: ToolRegistry):
    """If LLM continuously calls tools, agent breaks after max_iterations and calls chat for final answer."""
    mock_llm.chat_with_tools = AsyncMock(
        return_value=LLMResponseWithTools(
            content="",
            model="test-qwen-model",
            tool_calls=[ToolCall(name="get_battery_status", arguments={})],
        )
    )

    agent = NyxAgent(llm_provider=mock_llm, tool_registry=sample_tool_registry, max_iterations=2)
    response = await agent.run("Keep looping")

    assert response.iterations == 2
    assert response.tool_used == "get_battery_status"
    assert response.content == "Synthesized final response from available data."
