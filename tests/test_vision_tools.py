"""
tests/test_vision_tools.py

Unit tests for NyxAI desktop vision and screen awareness tools.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.agent.router import DomainClassifier
from core.agent.schemas import ToolResult
from core.agent.tool_registry import build_default_registry
from safety.permissions import PermissionLevel
from safety.policy import get_permission_level
from tools.vision.screen_tools import (
    CAPTURE_SCREEN_DEF,
    INSPECT_SCREEN_ERRORS_DEF,
    READ_SCREEN_TEXT_DEF,
    capture_screen,
    inspect_screen_for_errors,
    read_screen_text,
)


def test_vision_tool_definitions() -> None:
    assert CAPTURE_SCREEN_DEF.name == "capture_screen"
    assert CAPTURE_SCREEN_DEF.category == "vision"
    assert READ_SCREEN_TEXT_DEF.name == "read_screen_text"
    assert READ_SCREEN_TEXT_DEF.category == "vision"
    assert INSPECT_SCREEN_ERRORS_DEF.name == "inspect_screen_for_errors"
    assert INSPECT_SCREEN_ERRORS_DEF.category == "vision"


def test_vision_tool_safety_policy() -> None:
    assert get_permission_level("capture_screen") == PermissionLevel.SAFE
    assert get_permission_level("read_screen_text") == PermissionLevel.SAFE
    assert get_permission_level("inspect_screen_for_errors") == PermissionLevel.SAFE


def test_vision_tools_registered_in_default_registry() -> None:
    registry = build_default_registry()
    tool_names = registry.get_tool_names()
    assert "capture_screen" in tool_names
    assert "read_screen_text" in tool_names
    assert "inspect_screen_for_errors" in tool_names
    assert "vision" in registry.get_categories()


def test_router_classifies_vision_queries() -> None:
    router = DomainClassifier()
    assert "vision" in router.classify("take a screenshot of my screen")
    assert "vision" in router.classify("what is on my screen right now?")
    assert "vision" in router.classify("check my screen for errors")
    assert "vision" in router.classify("look at my screen and tell me what you see")


@patch("tools.vision.screen_tools.subprocess.run")
@patch("tools.vision.screen_tools._find_screenshot_utility")
@patch("os.path.exists")
@patch("os.path.getsize")
def test_capture_screen_success(
    mock_getsize: MagicMock,
    mock_exists: MagicMock,
    mock_find_util: MagicMock,
    mock_run: MagicMock,
) -> None:
    mock_find_util.return_value = ("spectacle", ["spectacle", "-b", "-n"])
    mock_exists.return_value = True
    mock_getsize.return_value = 1024 * 150  # 150 KB
    mock_run.return_value = MagicMock(returncode=0)

    result = capture_screen(mode="fullscreen", output_path="/tmp/test_shot.png")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data["path"] == "/tmp/test_shot.png"
    assert result.data["size_kb"] == 150.0
    assert "Screenshot captured successfully" in (result.display_text or "")


@patch("tools.vision.screen_tools.subprocess.run")
@patch("tools.vision.screen_tools._capture_screen_file")
@patch("shutil.which")
def test_read_screen_text_success(
    mock_which: MagicMock,
    mock_capture_file: MagicMock,
    mock_run: MagicMock,
) -> None:
    mock_which.return_value = "/usr/bin/tesseract"
    mock_capture_file.return_value = {
        "success": True,
        "path": "/tmp/dummy.png",
        "size_kb": 120.0,
    }
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="Hello World\nLine 2 text from IDE\n",
    )

    result = read_screen_text(mode="fullscreen")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data["line_count"] == 2
    assert "Hello World" in result.data["text"]
    assert "Screen Text Extracted" in (result.display_text or "")


@patch("tools.vision.screen_tools._read_screen_text_data")
def test_inspect_screen_for_errors_detected(mock_read_data: MagicMock) -> None:
    mock_read_data.return_value = {
        "success": True,
        "text": (
            "Building project...\n"
            "Traceback (most recent call last):\n"
            "  File 'main.py', line 12, in <module>\n"
            "ZeroDivisionError: division by zero\n"
            "Process terminated with exit code 1"
        ),
        "line_count": 5,
        "character_count": 130,
        "image_path": "/tmp/err.png",
    }

    result = inspect_screen_for_errors()
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data["has_errors"] is True
    assert result.data["error_count"] > 0
    assert "ZeroDivisionError" in (result.display_text or "")
    assert "Found" in (result.display_text or "")


@patch("tools.vision.screen_tools._read_screen_text_data")
def test_inspect_screen_for_errors_clean(mock_read_data: MagicMock) -> None:
    mock_read_data.return_value = {
        "success": True,
        "text": "All 286 tests passed successfully in 3.5s.\nReady.",
        "line_count": 2,
        "character_count": 48,
        "image_path": "/tmp/clean.png",
    }

    result = inspect_screen_for_errors()
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data["has_errors"] is False
    assert "No obvious stack traces or compiler errors detected" in (result.display_text or "")

