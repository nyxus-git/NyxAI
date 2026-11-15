"""
tests/test_music_tools.py

Unit tests for NyxAI Linux MPRIS media controller and local music tools.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.agent.router import DomainClassifier
from core.agent.schemas import ToolResult
from core.agent.tool_registry import build_default_registry
from safety.permissions import PermissionLevel
from safety.policy import get_permission_level
from tools.music.music_tools import (
    CONTROL_MUSIC_DEF,
    GET_CURRENT_TRACK_DEF,
    PLAY_LOCAL_MUSIC_DEF,
    control_music,
    get_current_track,
    play_local_music,
)


def test_music_tool_definitions() -> None:
    assert CONTROL_MUSIC_DEF.name == "control_music"
    assert CONTROL_MUSIC_DEF.category == "media"
    assert GET_CURRENT_TRACK_DEF.name == "get_current_track"
    assert GET_CURRENT_TRACK_DEF.category == "media"
    assert PLAY_LOCAL_MUSIC_DEF.name == "play_local_music"
    assert PLAY_LOCAL_MUSIC_DEF.category == "media"


def test_music_tool_safety_policy() -> None:
    assert get_permission_level("control_music") == PermissionLevel.SAFE
    assert get_permission_level("get_current_track") == PermissionLevel.SAFE
    assert get_permission_level("play_local_music") == PermissionLevel.CONFIRMATION


def test_music_tools_in_default_registry() -> None:
    registry = build_default_registry()
    tool_names = registry.get_tool_names()
    assert "control_music" in tool_names
    assert "get_current_track" in tool_names
    assert "play_local_music" in tool_names


def test_router_classifies_music_queries() -> None:
    router = DomainClassifier()
    assert "media" in router.classify("what song is playing right now?")
    assert "media" in router.classify("pause the music please")
    assert "media" in router.classify("skip song")
    assert "media" in router.classify("play local music")
    assert "media" in router.classify("turn the music volume up")


@patch("shutil.which")
@patch("tools.music.music_tools.subprocess.run")
def test_control_music_play(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/playerctl"
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    res = control_music(action="play")
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert "play" in (res.display_text or "")
    mock_run.assert_called_once_with(["playerctl", "play"], capture_output=True, text=True, timeout=3.0)


@patch("shutil.which")
@patch("tools.music.music_tools.subprocess.run")
def test_control_music_volume_set(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/playerctl"
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    res = control_music(action="volume_set", volume_level=0.7)
    assert res.success is True
    mock_run.assert_called_once_with(["playerctl", "volume", "0.70"], capture_output=True, text=True, timeout=3.0)


@patch("shutil.which")
@patch("tools.music.music_tools.subprocess.run")
def test_control_music_specific_player(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/playerctl"
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    res = control_music(action="pause", player="spotify")
    assert res.success is True
    mock_run.assert_called_once_with(["playerctl", "-p", "spotify", "pause"], capture_output=True, text=True, timeout=3.0)


@patch("shutil.which")
@patch("tools.music.music_tools.subprocess.run")
def test_get_current_track_playing(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/playerctl"

    # Call 1: playerctl status -> Playing
    # Call 2: playerctl metadata -> spotify|Playing|A.R. Rahman|Jai Ho|Slumdog Millionaire
    status_mock = MagicMock(returncode=0, stdout="Playing\n")
    meta_mock = MagicMock(returncode=0, stdout="spotify|Playing|A.R. Rahman|Jai Ho|Slumdog Millionaire\n")
    mock_run.side_effect = [status_mock, meta_mock]

    res = get_current_track()
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert res.data["playing"] is True
    assert res.data["artist"] == "A.R. Rahman"
    assert res.data["title"] == "Jai Ho"
    assert "Jai Ho" in (res.display_text or "")


@patch("shutil.which")
@patch("tools.music.music_tools.subprocess.run")
def test_get_current_track_no_players(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/playerctl"
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No players found")

    res = get_current_track()
    assert res.success is True
    assert res.data["playing"] is False
    assert "No active media playback detected" in (res.display_text or "")


@patch("shutil.which")
@patch("tools.music.music_tools.subprocess.Popen")
@patch("tools.music.music_tools._find_audio_files")
def test_play_local_music_found(
    mock_find: MagicMock,
    mock_popen: MagicMock,
    mock_which: MagicMock,
) -> None:
    mock_which.return_value = "/usr/bin/mpv"
    fake_track = Path("/home/user/Music/chill_beats.mp3")
    mock_find.return_value = [fake_track]

    res = play_local_music(query="chill")
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert res.data["filename"] == "chill_beats.mp3"
    assert "chill_beats.mp3" in (res.display_text or "")
    mock_popen.assert_called_once()


@patch("shutil.which")
@patch("tools.music.music_tools._find_audio_files")
def test_play_local_music_none_found(
    mock_find: MagicMock,
    mock_which: MagicMock,
) -> None:
    mock_which.return_value = "/usr/bin/mpv"
    mock_find.return_value = []

    res = play_local_music(query="nonexistent")
    assert isinstance(res, ToolResult)
    assert res.success is False
    assert "No local audio files" in (res.error or "")
    assert "YouTube instead" in (res.display_text or "")
