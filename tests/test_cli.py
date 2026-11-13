"""
tests/test_cli.py

Unit tests for the NyxAI Unified Command Line Interface (CLI)
in apps/cli/main.py.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from apps.cli.main import (
    main,
    query_backend_chat,
    query_local_fallback,
    run_daemon_command,
    run_master_routine,
    run_system_diagnostics,
)


class TestNyxCLI:
    """Tests for the nyx terminal command tool."""

    @pytest.mark.asyncio
    async def test_query_backend_chat_success(self) -> None:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Battery is currently at 88%."}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            reply = await query_backend_chat("What is my battery level?")
            assert "Battery is currently at 88%." in reply

    @pytest.mark.asyncio
    async def test_query_backend_chat_fallback_on_connect_error(self) -> None:
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")), \
             patch("apps.cli.main.query_local_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = "Local fallback response"
            reply = await query_backend_chat("Hello")
            assert mock_fallback.called
            assert reply == "Local fallback response"

    @pytest.mark.asyncio
    async def test_run_master_routine_api_success(self, capsys: pytest.CaptureFixture) -> None:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "JARVIS Morning Briefing complete."}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            await run_master_routine()
            out = capsys.readouterr().out
            assert "JARVIS Activation" in out
            assert "JARVIS Morning Briefing complete." in out

    @pytest.mark.asyncio
    async def test_run_system_diagnostics(self, capsys: pytest.CaptureFixture) -> None:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "cpu": {"percent": 14.2, "core_count": 16},
            "ram": {"used_gb": 6.4, "total_gb": 15.3, "percent": 41.8},
            "gpu": {"name": "NVIDIA GeForce RTX 4050 Laptop GPU", "available": True},
            "battery": {"percent": 95.0, "plugged_in": True},
            "uptime": "3h 42m",
            "agents": [{"name": "NyxSupervisor", "status": "active", "role": "Coordinator"}],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            await run_system_diagnostics()
            out = capsys.readouterr().out
            assert "Hardware Telemetry" in out
            assert "14.2%" in out
            assert "RTX 4050" in out
            assert "NyxSupervisor" in out

    @pytest.mark.asyncio
    async def test_run_daemon_command_missing_socket(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        with patch("apps.cli.main.SOCKET_PATH", tmp_path / "non_existent.sock"):
            await run_daemon_command("status")
            out = capsys.readouterr().out
            assert "socket not found" in out.lower()

    @pytest.mark.asyncio
    async def test_run_daemon_command_over_socket(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        sock_file = tmp_path / "test_nyx_cli.sock"

        async def _fake_daemon(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.readline()
            writer.write(b'{"status": "ok", "running": true}\n')
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_unix_server(_fake_daemon, path=str(sock_file))

        try:
            with patch("apps.cli.main.SOCKET_PATH", sock_file):
                await run_daemon_command("status")
                out = capsys.readouterr().out
                assert '"status": "ok"' in out
        finally:
            server.close()
            await server.wait_closed()

    def test_cli_subcommand_dispatch_system(self) -> None:
        with patch("sys.argv", ["nyx", "system"]), \
             patch("asyncio.run") as mock_run:
            main()
            assert mock_run.called
            # Clean up coroutine
            coro = mock_run.call_args[0][0]
            coro.close()

    def test_cli_prompt_argument_dispatch(self) -> None:
        with patch("sys.argv", ["nyx", "check battery"]), \
             patch("asyncio.run") as mock_run:
            main()
            assert mock_run.called
            coro = mock_run.call_args[0][0]
            coro.close()

