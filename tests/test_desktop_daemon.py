"""
tests/test_desktop_daemon.py

Unit tests for Linux Desktop Daemon, Hands-Free Voice Listener integration,
notify-send desktop notifications, and Unix Domain Socket IPC.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from apps.desktop.main import (
    main,
    run_daemon,
    run_hands_free_listener_task,
    send_desktop_notification,
)


class TestDesktopDaemon:
    """Tests for desktop daemon IPC and desktop notifications."""

    def test_send_desktop_notification_invokes_notify_send(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/notify-send"), \
             patch("subprocess.Popen") as mock_popen:
            send_desktop_notification("NyxAI Notification", "System ready.")
            assert mock_popen.called
            args = mock_popen.call_args[0][0]
            assert "notify-send" in args
            assert "NyxAI Notification" in args
            assert "System ready." in args

    def test_send_desktop_notification_graceful_when_missing(self) -> None:
        with patch("shutil.which", return_value=None), \
             patch("subprocess.Popen") as mock_popen:
            send_desktop_notification("NyxAI Notification", "System ready.")
            assert not mock_popen.called

    @pytest.mark.asyncio
    async def test_daemon_ipc_socket_commands(self, tmp_path: Path) -> None:
        sock_file = tmp_path / "test_nyx.sock"

        with patch("apps.desktop.main.SOCKET_PATH", sock_file):
            stop_event = asyncio.Event()

            # Start daemon in background task
            daemon_task = asyncio.create_task(run_daemon(hands_free=False))
            # Give server a moment to start
            await asyncio.sleep(0.05)

            try:
                # 1. Connect as IPC client and send "status"
                reader, writer = await asyncio.open_unix_connection(str(sock_file))
                writer.write(b"status\n")
                await writer.drain()
                line = await reader.readline()
                data = json.loads(line.decode())
                assert data["status"] == "ok"
                assert data["running"] is True
                assert data["hands_free"] is False
                writer.close()
                await writer.wait_closed()

                # 2. Connect as IPC client and send "toggle-ui"
                with patch("apps.desktop.main.toggle_ui", return_value=True):
                    reader, writer = await asyncio.open_unix_connection(str(sock_file))
                    writer.write(b"toggle-ui\n")
                    await writer.drain()
                    line = await reader.readline()
                    data = json.loads(line.decode())
                    assert data["status"] == "ok"
                    assert data["success"] is True
                    writer.close()
                    await writer.wait_closed()

            finally:
                daemon_task.cancel()
                await asyncio.gather(daemon_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_hands_free_listener_task_stop_event(self) -> None:
        stop_event = asyncio.Event()
        stop_event.set()  # Already stopped

        # Should exit immediately without hanging
        await run_hands_free_listener_task(stop_event, wake_word="hey_jarvis")
        assert stop_event.is_set()

    def test_cli_argument_parsing_daemon_hands_free(self) -> None:
        with patch("sys.argv", ["apps/desktop/main.py", "daemon", "--hands-free", "--wake-word", "hey_jarvis"]), \
             patch("asyncio.run") as mock_run:
            main()
            assert mock_run.called
            coro = mock_run.call_args[0][0]
            coro.close()
