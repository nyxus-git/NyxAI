"""
tests/test_multi_agent_pipeline.py

End-to-End integration test suite for NyxAI Next-Level Multi-Agent Architecture:
  1. Wake word & Audio Chime generation
  2. Domain Classifier pruning & prompt optimization
  3. Multi-Agent Supervisor orchestration (TerminalAgent, MediaAgent, CommsAgent, RoutineAgent)
  4. JARVIS "Activate All Tasks" master composite routine
  5. Sandboxed Shell execution & safety policies
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent.router import DomainClassifier
from core.agent.schemas import ToolCall, ToolDomain
from core.agent.supervisor import NyxSupervisor
from core.agent.tool_registry import build_default_registry
from core.brain.llm import LLMProvider, LLMResponseWithTools
from voice.wakeword.chime import generate_activation_chime, to_wav_bytes


def make_mock_llm(model: str = "qwen2.5:3b") -> MagicMock:
    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.get_model_name.return_value = model
    mock_llm.health_check = AsyncMock(return_value=True)

    async def fake_chat_with_tools(messages, tools, temperature=0.5):
        return LLMResponseWithTools(
            content="I am ready to assist with your next-level tasks, Rohan.",
            model=model,
            tool_calls=[],
        )

    mock_llm.chat_with_tools = AsyncMock(side_effect=fake_chat_with_tools)
    return mock_llm


@pytest.mark.asyncio
async def test_wake_chime_generation_integration():
    """Verify wake word chimes generate valid RIFF WAV audio bytes in-memory."""
    pcm = generate_activation_chime(sample_rate=16000)
    assert len(pcm) > 0
    wav_bytes = to_wav_bytes(pcm, sample_rate=16000)
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:16]


@pytest.mark.asyncio
async def test_domain_classifier_pruning_integration():
    """Verify domain router correctly prunes tools to domain sets."""
    registry = build_default_registry()
    classifier = DomainClassifier()

    # Terminal command classification
    domains = classifier.classify("run terminal command git status")
    assert "terminal" in domains
    terminal_tools = registry.get_tools_for_ollama(categories=domains)
    tool_names = [t["function"]["name"] for t in terminal_tools]
    assert "execute_terminal_command" in tool_names

    # Media / YouTube classification
    domains = classifier.classify("play lo-fi beats on youtube")
    assert "media" in domains
    media_tools = registry.get_tools_for_ollama(categories=domains)
    tool_names = [t["function"]["name"] for t in media_tools]
    assert "play_youtube" in tool_names or "control_media" in tool_names


@pytest.mark.asyncio
async def test_supervisor_master_routine_integration():
    """Verify NyxSupervisor executes 'activate all tasks' master routine end-to-end."""
    registry = build_default_registry()
    llm = make_mock_llm()
    supervisor = NyxSupervisor(llm_provider=llm, tool_registry=registry)

    response = await supervisor.run("Hey Nyx, activate all tasks")
    assert response.tool_used == "activate_all_tasks"
    assert "jarvis routine activated" in response.content.lower() or "all tasks activated" in response.content.lower()
    assert response.tool_result is not None
    assert "hardware" in response.tool_result
    assert "comms" in response.tool_result


@pytest.mark.asyncio
async def test_supervisor_youtube_fastpath_integration():
    """Verify supervisor fast-paths YouTube video search without hallucination."""
    registry = build_default_registry()
    llm = make_mock_llm()
    supervisor = NyxSupervisor(llm_provider=llm, tool_registry=registry)

    response = await supervisor.run("play synthwave chill radio on youtube")
    assert response.tool_used == "play_youtube"
    assert response.tool_result is not None
    assert "synthwave chill radio" in response.tool_result.get("query", "")


@pytest.mark.asyncio
async def test_supervisor_sandboxed_terminal_integration():
    """Verify terminal agent executes valid non-prohibited commands."""
    registry = build_default_registry()
    llm = make_mock_llm()
    supervisor = NyxSupervisor(llm_provider=llm, tool_registry=registry)

    result = await supervisor.terminal_agent.execute("execute_terminal_command", {"command": "echo 'MULTI AGENT ONLINE'"})
    assert result.success is True
    assert "MULTI AGENT ONLINE" in result.data["stdout"]
