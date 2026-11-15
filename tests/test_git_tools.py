"""
tests/test_git_tools.py

Unit tests for NyxAI Autonomous Developer and Git Workflow tools.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.agent.router import DomainClassifier
from core.agent.schemas import ToolResult
from core.agent.tool_registry import build_default_registry
from safety.permissions import PermissionLevel
from safety.policy import get_permission_level
from tools.dev.git_tools import (
    GIT_COMMIT_DEF,
    GIT_DIFF_DEF,
    GIT_LOG_DEF,
    GIT_STATUS_DEF,
    git_commit,
    git_diff,
    git_log,
    git_status,
)


def test_git_tool_definitions() -> None:
    assert GIT_STATUS_DEF.name == "git_status"
    assert GIT_STATUS_DEF.category == "terminal"
    assert GIT_DIFF_DEF.name == "git_diff"
    assert GIT_DIFF_DEF.category == "terminal"
    assert GIT_LOG_DEF.name == "git_log"
    assert GIT_LOG_DEF.category == "terminal"
    assert GIT_COMMIT_DEF.name == "git_commit"
    assert GIT_COMMIT_DEF.category == "terminal"


def test_git_tool_safety_policy() -> None:
    assert get_permission_level("git_status") == PermissionLevel.SAFE
    assert get_permission_level("git_diff") == PermissionLevel.SAFE
    assert get_permission_level("git_log") == PermissionLevel.SAFE
    assert get_permission_level("git_commit") == PermissionLevel.CONFIRMATION


def test_git_tools_in_default_registry() -> None:
    registry = build_default_registry()
    names = registry.get_tool_names()
    assert "git_status" in names
    assert "git_diff" in names
    assert "git_log" in names
    assert "git_commit" in names


def test_router_classifies_git_queries() -> None:
    router = DomainClassifier()
    assert "terminal" in router.classify("what is my git status?")
    assert "terminal" in router.classify("show git diff")
    assert "terminal" in router.classify("what changed in git?")
    assert "terminal" in router.classify("show recent commits")


@patch("shutil.which")
@patch("tools.dev.git_tools.subprocess.run")
def test_git_status_parsed(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/git"
    stdout_sample = (
        "## main...origin/main\n"
        "M  tools/vision/screen_tools.py\n"
        " M core/agent/router.py\n"
        "?? tools/dev/git_tools.py\n"
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=stdout_sample, stderr="")

    res = git_status()
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert res.data["branch"] == "main"
    assert "tools/vision/screen_tools.py" in res.data["staged"]
    assert "core/agent/router.py" in res.data["unstaged"]
    assert "tools/dev/git_tools.py" in res.data["untracked"]
    assert "Branch: **main**" in (res.display_text or "")


@patch("shutil.which")
@patch("tools.dev.git_tools.subprocess.run")
def test_git_diff_output(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/git"
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="diff --git a/foo.py b/foo.py\n+print('hello')\n",
        stderr="",
    )

    res = git_diff(staged=True)
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert "```diff" in (res.display_text or "")
    assert "+print('hello')" in (res.display_text or "")


@patch("shutil.which")
@patch("tools.dev.git_tools.subprocess.run")
def test_git_log_parsed(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/git"
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=(
            "a1b2c3d|Nyx Dev|2 hours ago|feat: add multimodal screen vision\n"
            "e4f5g6h|Nyx Dev|1 day ago|refactor: improve tts speed\n"
        ),
        stderr="",
    )

    res = git_log(count=2)
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert res.data["count"] == 2
    assert res.data["commits"][0]["hash"] == "a1b2c3d"
    assert res.data["commits"][0]["subject"] == "feat: add multimodal screen vision"
    assert "Recent 2 Commits" in (res.display_text or "")


@patch("shutil.which")
@patch("tools.dev.git_tools.subprocess.run")
def test_git_commit_success(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/git"
    # Call 1: git add -A
    # Call 2: git commit -m
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=0, stdout="[main 987abcd] feat: new git tools\n 2 files changed", stderr=""),
    ]

    res = git_commit(message="feat: new git tools", add_all=True)
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert "Changes committed successfully" in (res.display_text or "")


def test_git_commit_empty_message() -> None:
    res = git_commit(message="   ")
    assert res.success is False
    assert "Commit message cannot be empty" in (res.error or "")

