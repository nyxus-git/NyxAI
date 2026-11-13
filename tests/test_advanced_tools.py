"""
tests/test_advanced_tools.py

Unit tests for Terminal execution, YouTube & Media controls,
Communications Hub, and NyxSupervisor Multi-Agent orchestration.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent.schemas import ToolResult
from core.agent.supervisor import NyxSupervisor
from core.agent.tool_registry import build_default_registry
from core.brain.llm import LLMProvider, LLMResponseWithTools
from tools.comms.comms_tools import (
    activate_all_tasks,
    check_emails,
    check_telegram,
    send_discord_alert,
)
from tools.terminal.terminal_tools import execute_terminal_command
from tools.youtube.youtube_tools import control_media, play_youtube


class TestTerminalTools:
    """Tests for sandboxed bash terminal command runner."""

    @pytest.mark.asyncio
    async def test_echo_command_execution(self) -> None:
        result = await execute_terminal_command("echo 'NyxAI Terminal Ready'")
        assert result.success is True
        assert result.data is not None
        assert result.data["returncode"] == 0
        assert "NyxAI Terminal Ready" in result.data["stdout"]

    @pytest.mark.asyncio
    async def test_prohibited_sudo_command_blocked(self) -> None:
        result = await execute_terminal_command("sudo apt update")
        assert result.success is False
        assert "prohibited by safety policy" in result.error

    @pytest.mark.asyncio
    async def test_prohibited_rm_rf_blocked(self) -> None:
        result = await execute_terminal_command("rm -rf /")
        assert result.success is False
        assert "prohibited" in result.error

        result_home = await execute_terminal_command("rm -rf ~")
        assert result_home.success is False

    @pytest.mark.asyncio
    async def test_prohibited_reboot_blocked(self) -> None:
        result = await execute_terminal_command("reboot")
        assert result.success is False
        assert "prohibited" in result.error

    @pytest.mark.asyncio
    async def test_empty_command_handled(self) -> None:
        result = await execute_terminal_command("   ")
        assert result.success is False


class TestYouTubeAndMediaTools:
    """Tests for YouTube search & playback and media controls."""

    def test_play_youtube_url_generation(self) -> None:
        result = play_youtube("lofi hip hop beats")
        assert result.success is True
        assert result.data is not None
        assert "youtube.com/results?search_query=lofi+hip+hop+beats" in result.data["url"]

    def test_play_youtube_empty_query_fails(self) -> None:
        result = play_youtube("")
        assert result.success is False

    def test_control_media_invalid_action(self) -> None:
        result = control_media("unknown_action_xyz")
        assert result.success is False
        assert "Unknown media action" in result.error


class TestCommunicationsHub:
    """Tests for Email, Telegram, Discord, and activate_all_tasks routine."""

    @pytest.mark.asyncio
    async def test_check_emails_unconfigured_guidance(self) -> None:
        # Without IMAP_SERVER in env, returns helpful configuration prompt
        result = await check_emails()
        assert result.success is True
        assert result.data["configured"] is False
        assert "IMAP_SERVER" in result.display_text

    @pytest.mark.asyncio
    async def test_check_telegram_unconfigured_guidance(self) -> None:
        result = await check_telegram()
        assert result.success is True
        assert result.data["configured"] is False
        assert "TELEGRAM_BOT_TOKEN" in result.display_text

    @pytest.mark.asyncio
    async def test_send_discord_alert_unconfigured(self) -> None:
        result = await send_discord_alert("Test Alert")
        assert result.success is True
        assert result.data["configured"] is False
        assert "DISCORD_WEBHOOK_URL" in result.display_text

    @pytest.mark.asyncio
    async def test_send_discord_alert_empty_message(self) -> None:
        result = await send_discord_alert("")
        assert result.success is False
        assert "cannot be empty" in result.error

    @pytest.mark.asyncio
    async def test_activate_all_tasks_routine(self) -> None:
        result = await activate_all_tasks()
        assert result.success is True
        assert result.data is not None
        assert "hardware" in result.data
        assert "tasks" in result.data
        assert "comms" in result.data
        assert "JARVIS Routine Activated" in result.display_text


class TestNyxSupervisor:
    """Tests for Supervisor multi-agent orchestration and delegation."""

    @pytest.mark.asyncio
    async def test_supervisor_fast_paths_activate_all_tasks(self) -> None:
        registry = build_default_registry()
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.get_model_name.return_value = "qwen2.5:3b"

        supervisor = NyxSupervisor(llm_provider=mock_llm, tool_registry=registry)
        response = await supervisor.run("Hey Nyx, activate all tasks")

        assert response.tool_used == "activate_all_tasks"
        assert "JARVIS Routine Activated" in response.content

    @pytest.mark.asyncio
    async def test_supervisor_fast_paths_youtube_playback(self) -> None:
        registry = build_default_registry()
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.get_model_name.return_value = "qwen2.5:3b"

        supervisor = NyxSupervisor(llm_provider=mock_llm, tool_registry=registry)
        response = await supervisor.run("play Interstellar soundtrack on youtube")

        assert response.tool_used == "play_youtube"
        assert "Opening YouTube for 'Interstellar soundtrack'" in response.content

