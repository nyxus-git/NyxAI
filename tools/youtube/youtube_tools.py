"""
tools/youtube/youtube_tools.py

YouTube search & playback and Linux media playback controller for NyxAI.

Capabilities:
  - Search and open YouTube videos/music in user's default browser or background player
  - Control active media playback across Linux desktops (KDE, GNOME, Hyprland) using MPRIS playerctl
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.parse
import webbrowser
from typing import Any

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

# ── Tool Definitions ───────────────────────────────────────────────────────────

PLAY_YOUTUBE_DEF = ToolDefinition(
    name="play_youtube",
    description=(
        "Search and open a YouTube video or music in the user's web browser. "
        "Use this when the user asks to play a song, video, lo-fi stream, or tutorial on YouTube. "
        "Examples: 'play lo-fi beats on YouTube', 'open Bohemian Rhapsody on YouTube'."
    ),
    parameters={
        "query": ToolParameter(
            type="string",
            description="The search query for the video/song (e.g. 'lofi hip hop', 'queen bohemian rhapsody').",
            required=True,
        ),
    },
    category="media",
)

CONTROL_MEDIA_DEF = ToolDefinition(
    name="control_media",
    description=(
        "Control active media playback across Linux (play, pause, next, previous, volume). "
        "Works with Spotify, YouTube browser tabs, VLC, MPV, and all MPRIS-compliant players."
    ),
    parameters={
        "action": ToolParameter(
            type="string",
            description="Playback action to perform.",
            enum=["play", "pause", "play-pause", "next", "previous", "stop", "volume_up", "volume_down"],
            required=True,
        ),
    },
    category="media",
)


def play_youtube(query: str) -> ToolResult:
    """
    Search and launch YouTube playback in the default browser.

    Args:
        query: Search term for the song or video.

    Returns:
        ToolResult with the launched URL and status.
    """
    clean_query = query.strip()
    if not clean_query:
        return ToolResult(
            tool_name="play_youtube",
            success=False,
            error="Search query cannot be empty.",
        )

    # Encode query for direct search
    encoded = urllib.parse.quote_plus(clean_query)
    url = f"https://www.youtube.com/results?search_query={encoded}"

    logger.info("playing_youtube_query", query=clean_query, url=url)

    try:
        opened = webbrowser.open(url)
        if not opened and shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            opened = True

        return ToolResult(
            tool_name="play_youtube",
            success=True,
            data={"query": clean_query, "url": url},
            display_text=f"Opening YouTube for '{clean_query}': {url}",
        )
    except Exception as e:
        logger.exception("play_youtube_failed", error=str(e))
        return ToolResult(
            tool_name="play_youtube",
            success=False,
            error=f"Failed to open YouTube: {str(e)}",
        )


def control_media(action: str) -> ToolResult:
    """
    Control active Linux desktop media playback via playerctl.

    Args:
        action: play, pause, play-pause, next, previous, stop, volume_up, volume_down.

    Returns:
        ToolResult indicating playback control status.
    """
    clean_act = action.strip().lower()

    if not shutil.which("playerctl"):
        logger.warning("playerctl_not_installed")
        return ToolResult(
            tool_name="control_media",
            success=False,
            error="playerctl is not installed on this system. Install it via 'sudo pacman -S playerctl' or 'sudo apt install playerctl'.",
            display_text="playerctl is not installed to control desktop media.",
        )

    cmd: list[str] = ["playerctl"]
    if clean_act in ("play", "pause", "play-pause", "next", "previous", "stop"):
        cmd.append(clean_act)
    elif clean_act == "volume_up":
        cmd.extend(["volume", "0.05+"])
    elif clean_act == "volume_down":
        cmd.extend(["volume", "0.05-"])
    else:
        return ToolResult(
            tool_name="control_media",
            success=False,
            error=f"Unknown media action '{action}'.",
        )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            logger.info("media_control_executed", action=clean_act)
            return ToolResult(
                tool_name="control_media",
                success=True,
                data={"action": clean_act},
                display_text=f"Media action '{clean_act}' executed successfully.",
            )
        else:
            err = proc.stderr.strip() or "No active media players found."
            logger.info("media_control_no_player", error=err)
            return ToolResult(
                tool_name="control_media",
                success=False,
                error=err,
                display_text=f"Media control: {err}",
            )
    except Exception as e:
        logger.exception("media_control_failed", error=str(e))
        return ToolResult(
            tool_name="control_media",
            success=False,
            error=str(e),
        )

