"""
tests/test_deployment.py

Unit tests for persistent deployment & system integration.

Tests:
  - Systemd user service unit definitions (syntax, directives, restart policy)
  - Shell management scripts (executable status, syntax, help output)
  - Desktop companion controller (CLI parsing, status checker)
"""

import configparser
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.desktop.main import is_hyprland, check_status

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_DIR = PROJECT_ROOT / "deployment" / "systemd"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


class TestSystemdUnits:
    """Validate systemd user unit definitions."""

    @pytest.mark.parametrize("service_name", ["nyxai-core.service", "nyxai-ui.service", "nyxai-voice.service"])
    def test_service_file_structure(self, service_name: str):
        """All unit files must exist, be non-empty, and contain valid Unit/Service/Install sections."""
        path = DEPLOYMENT_DIR / service_name
        assert path.exists(), f"Missing unit file: {service_name}"
        assert path.stat().st_size > 50, f"Unit file {service_name} is too small"

        # Systemd unit files follow standard INI format; strict=False allows repeated Environment= directives
        config = configparser.ConfigParser(strict=False, interpolation=None)
        config.read(str(path))

        assert "Unit" in config, f"{service_name} missing [Unit]"
        assert "Service" in config, f"{service_name} missing [Service]"
        assert "Install" in config, f"{service_name} missing [Install]"

        service_section = config["Service"]
        assert "ExecStart" in service_section
        assert service_section.get("Restart") == "on-failure"
        assert "RestartSec" in service_section

        install_section = config["Install"]
        assert install_section.get("WantedBy") == "default.target"

    def test_core_service_environment(self):
        """nyxai-core.service must pass proper unbuffered python environment."""
        path = DEPLOYMENT_DIR / "nyxai-core.service"
        content = path.read_text()
        assert "uvicorn api.app.main:app" in content
        assert "PYTHONUNBUFFERED=1" in content


class TestDeploymentScripts:
    """Validate installer and run script permissions and syntax."""

    def test_scripts_executable(self):
        """Scripts must have execute permission bit set."""
        for script in ["install.sh", "run.sh"]:
            path = SCRIPTS_DIR / script
            assert path.exists(), f"Missing script: {script}"
            assert os.access(path, os.X_OK), f"Script {script} is not executable"

    def test_run_script_help(self):
        """run.sh help should execute cleanly without error."""
        res = subprocess.run(
            [str(SCRIPTS_DIR / "run.sh"), "help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert res.returncode == 0
        assert "NyxAI Service & Lifecycle Manager" in res.stdout
        assert "start" in res.stdout
        assert "stop" in res.stdout

    def test_install_script_syntax(self):
        """install.sh must pass bash syntax check and expose --help."""
        syntax = subprocess.run(
            ["bash", "-n", str(SCRIPTS_DIR / "install.sh")],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert syntax.returncode == 0, syntax.stderr
        help_res = subprocess.run(
            [str(SCRIPTS_DIR / "install.sh"), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert help_res.returncode == 0
        assert "NyxAI Linux Installer" in help_res.stdout


class TestDesktopController:
    """Validate apps/desktop/main.py behavior."""

    def test_is_hyprland_false_when_no_env(self):
        """Should return False if HYPRLAND_INSTANCE_SIGNATURE is unset."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_hyprland() is False

    @pytest.mark.asyncio
    async def test_check_status_healthy(self):
        """check_status should report healthy when backend responds with 200."""
        mock_response = {
            "status": "healthy",
            "llm": {"provider": "ollama", "model": "qwen2.5:3b", "healthy": True},
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            code = await check_status()
            assert code == 0

    @pytest.mark.asyncio
    async def test_check_status_unhealthy(self):
        """check_status should return 1 when backend is unreachable."""
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            code = await check_status()
            assert code == 1


class TestDesktopAppIPC:
    """Validate single-instance IPC ACK & frozen-instance cleanup in desktop_app.py."""

    def test_send_single_instance_command_returns_true_on_ack(self, tmp_path: Path):
        """Responsive instance replying 'ok' should return True."""
        import socket
        import threading
        from apps.desktop import desktop_app

        sock_path = tmp_path / "ipc.sock"
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(sock_path))
        srv.listen(1)

        received: list[bytes] = []

        def serve_once():
            conn, _ = srv.accept()
            with conn:
                received.append(conn.recv(64))
                conn.sendall(b"ok\n")

        t = threading.Thread(target=serve_once, daemon=True)
        t.start()

        try:
            with patch.object(desktop_app, "SOCKET_PATH", sock_path):
                ok = desktop_app.send_single_instance_command("show", timeout_s=1.0)
            assert ok is True
            t.join(timeout=1.0)
            assert received == [b"show\n"]
        finally:
            srv.close()

    def test_send_single_instance_command_cleans_up_unresponsive_socket(self, tmp_path: Path):
        """Frozen instance (accepting socket without ACK) must trigger recovery and return False."""
        import socket
        import threading
        from apps.desktop import desktop_app

        sock_path = tmp_path / "hung.sock"
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(sock_path))
        srv.listen(1)
        stop_event = threading.Event()

        def hold_without_reply():
            conn, _ = srv.accept()
            with conn:
                conn.recv(64)
                stop_event.wait(2.0)

        t = threading.Thread(target=hold_without_reply, daemon=True)
        t.start()

        try:
            with (
                patch.object(desktop_app, "SOCKET_PATH", sock_path),
                patch.object(desktop_app, "_find_desktop_app_pids", return_value=[]),
            ):
                ok = desktop_app.send_single_instance_command("show", timeout_s=0.15)
            assert ok is False
            assert not sock_path.exists()
        finally:
            stop_event.set()
            srv.close()
            t.join(timeout=1.0)
