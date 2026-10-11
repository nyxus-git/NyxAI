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
