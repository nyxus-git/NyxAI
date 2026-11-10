"""
tools/files/file_tools.py

File and application tools for NyxAI.

Tools:
  - open_application: Launch a desktop application by name across Linux DEs (KDE, GNOME, Hyprland, etc.)
"""

from __future__ import annotations

import os
import shutil
import subprocess

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

# Tool Definitions

OPEN_APPLICATION_DEF = ToolDefinition(
    name="open_application",
    description=(
        "Open or launch an application on the Linux desktop by its name. "
        "Use this when the user asks to open, start, or launch a specific program. "
        "Examples: 'open Firefox', 'launch VS Code', 'open terminal', 'open calculator'."
    ),
    parameters={
        "application": ToolParameter(
            type="string",
            description=(
                "The name of the application to open. Use the lowercase command name or common name. "
                "Examples: 'firefox', 'code', 'konsole', 'dolphin', 'spotify', 'discord', 'google-chrome'."
            ),
            required=True,
        ),
    },
    category="files",
)

_APP_CANDIDATES: dict[str, list[str]] = {
    "vscode": ["code", "codium"],
    "vs code": ["code", "codium"],
    "visual studio code": ["code", "codium"],
    "vscodium": ["codium", "vscodium"],
    "chrome": ["google-chrome-stable", "google-chrome", "chromium"],
    "google chrome": ["google-chrome-stable", "google-chrome", "chromium"],
    "google-chrome": ["google-chrome-stable", "google-chrome", "chromium"],
    "chromium-browser": ["chromium", "chromium-browser"],
    "brave": ["brave", "brave-browser"],
    "browser": ["firefox", "google-chrome-stable", "google-chrome", "chromium", "brave"],
    "terminal": ["konsole", "kitty", "alacritty", "wezterm", "gnome-terminal", "xfce4-terminal", "foot"],
    "files": ["dolphin", "thunar", "nautilus", "nemo"],
    "file manager": ["dolphin", "thunar", "nautilus", "nemo"],
    "calculator": ["kcalc", "gnome-calculator"],
    "settings": ["systemsettings", "gnome-control-center"],
    "telegram": ["telegram-desktop", "Telegram"],
}


def _resolve_launch_command(raw_name: str) -> list[str] | None:
    """Resolve an application name into an executable command list."""
    app_name = raw_name.strip().lower().strip("\"'")
    candidates = _APP_CANDIDATES.get(app_name, [app_name])

    for candidate in candidates:
        if shutil.which(candidate):
            return [candidate]

    # Fallback: try launching matching .desktop entry via gtk-launch if available
    if shutil.which("gtk-launch"):
        desktop_id = f"{candidates[0]}.desktop"
        for search_dir in ("/usr/share/applications", os.path.expanduser("~/.local/share/applications")):
            if os.path.exists(os.path.join(search_dir, desktop_id)):
                return ["gtk-launch", desktop_id]

    return None


def open_application(application: str) -> ToolResult:
    """
    Launch a desktop application in the background with the active desktop session env.
    """
    app_name = application.strip().lower().strip("\"'")
    logger.info("tool_open_application", application=app_name)

    cmd = _resolve_launch_command(app_name)
    if cmd is None:
        return ToolResult(
            tool_name="open_application",
            success=False,
            error=(
                f"Application '{application}' was not found on this system. "
                f"Make sure it is installed."
            ),
        )

    try:
        env = os.environ.copy()
        subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        launched_name = cmd[-1]
        data = {"application": launched_name, "launched": True}
        display = f"Opened '{launched_name}'."

        logger.info("tool_app_launched", application=launched_name, cmd=cmd)

        return ToolResult(
            tool_name="open_application",
            success=True,
            data=data,
            display_text=display,
        )

    except Exception as e:
        logger.error("tool_app_launch_failed", application=app_name, error=str(e))
        return ToolResult(
            tool_name="open_application",
            success=False,
            error=f"Failed to launch '{app_name}': {str(e)}",
        )
