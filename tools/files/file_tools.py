"""
tools/files/file_tools.py

File and application tools for NyxAI.

These tools have external effects (launching applications) and require
PermissionLevel.CONFIRMATION before execution.

Tools:
  - open_application: Launch an application by name using xdg-open / subprocess
"""

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
        "Examples: 'open Firefox', 'launch VS Code', 'start Spotify'."
    ),
    parameters={
        "application": ToolParameter(
            type="string",
            description=(
                "The name of the application to open. Use the lowercase command name. "
                "Examples: 'firefox', 'code', 'spotify', 'discord', 'thunar'."
            ),
            required=True,
        ),
    },
    category="files",
)


# Tool Implementations


def open_application(application: str) -> ToolResult:
    """
    Launch a desktop application.

    Uses subprocess to launch the application in the background.
    The application name is validated by the CommandValidator before this
    function is ever called — it only runs if the name passed validation.

    Args:
        application: The application command name (e.g. "firefox", "code").

    Returns:
        ToolResult indicating success or failure.
    """
    app_name = application.strip().lower()
    logger.info("tool_open_application", application=app_name)

    # Verify the binary exists on PATH before trying to launch
    if not shutil.which(app_name):
        # Some apps have different binary names — try common aliases
        aliases = {
            "vscode": "code",
            "vs code": "code",
            "vscodium": "codium",
            "chrome": "google-chrome",
            "chromium-browser": "chromium",
        }
        alt_name = aliases.get(app_name)
        if alt_name and shutil.which(alt_name):
            app_name = alt_name
        else:
            return ToolResult(
                tool_name="open_application",
                success=False,
                error=(
                    f"Application '{application}' not found on PATH. "
                    f"Make sure it's installed."
                ),
            )

    try:
        # Launch in background, detach from this process
        subprocess.Popen(
            [app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process
        )

        data = {"application": app_name, "launched": True}
        display = f"Opened '{app_name}' successfully."

        logger.info("tool_app_launched", application=app_name)

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
