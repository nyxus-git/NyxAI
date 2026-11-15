"""
tools/music/music_tools.py

Linux MPRIS Media Controller and Local Audio Player for NyxAI.

Provides:
  - control_music: Send play/pause/skip/volume commands to active MPRIS players via playerctl.
  - get_current_track: Query currently playing track metadata (title, artist, album, player status).
  - play_local_music: Find and play audio files from ~/Music using headless mpv.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

MUSIC_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"}

# ── Tool Definitions ───────────────────────────────────────────────────────────

CONTROL_MUSIC_DEF = ToolDefinition(
    name="control_music",
    description=(
        "Control active media playback across Linux desktops (Spotify, Firefox, Chrome, VLC, MPV) via MPRIS. "
        "Supports play, pause, play-pause, next, previous, stop, volume_up, volume_down, volume_set."
    ),
    parameters={
        "action": ToolParameter(
            type="string",
            description="Media action to perform: 'play', 'pause', 'play-pause', 'next', 'previous', 'stop', 'volume_up', 'volume_down', 'volume_set'.",
            enum=["play", "pause", "play-pause", "next", "previous", "stop", "volume_up", "volume_down", "volume_set"],
            required=True,
        ),
        "player": ToolParameter(
            type="string",
            description="Optional specific player name (e.g. 'spotify', 'firefox', 'mpv'). If omitted, controls active player.",
            required=False,
        ),
        "volume_level": ToolParameter(
            type="number",
            description="Target volume level for 'volume_set' (between 0.0 and 1.0, e.g. 0.5 for 50%).",
            required=False,
        ),
    },
    category="media",
)

GET_CURRENT_TRACK_DEF = ToolDefinition(
    name="get_current_track",
    description=(
        "Get metadata for the currently playing music track or media across Linux players (title, artist, album, player name, playback status). "
        "Use this when the user asks 'what song is playing', 'current track', or 'what's playing'."
    ),
    parameters={},
    category="media",
)

PLAY_LOCAL_MUSIC_DEF = ToolDefinition(
    name="play_local_music",
    description=(
        "Search and play a local audio file or song in ~/Music or local directory using background headless MPV player. "
        "Use this when the user asks to play a local song or audio file."
    ),
    parameters={
        "query": ToolParameter(
            type="string",
            description="Search keyword for the song title, artist, or file name.",
            required=False,
        ),
        "file_path": ToolParameter(
            type="string",
            description="Exact absolute path to the audio file if known.",
            required=False,
        ),
    },
    category="media",
)


# ── Implementation ─────────────────────────────────────────────────────────────

def control_music(
    action: str,
    player: str | None = None,
    volume_level: float | None = None,
) -> ToolResult:
    """
    Control active Linux desktop media playback via playerctl.
    """
    if not shutil.which("playerctl"):
        return ToolResult(
            tool_name="control_music",
            success=False,
            error="playerctl is not installed on this system.",
            display_text="playerctl is not installed to control desktop media.",
        )

    clean_act = action.strip().lower()
    cmd: list[str] = ["playerctl"]

    if player:
        cmd.extend(["-p", player.strip()])

    if clean_act in ("play", "pause", "play-pause", "next", "previous", "stop"):
        cmd.append(clean_act)
    elif clean_act == "volume_up":
        cmd.extend(["volume", "0.05+"])
    elif clean_act == "volume_down":
        cmd.extend(["volume", "0.05-"])
    elif clean_act == "volume_set":
        target = 0.5 if volume_level is None else max(0.0, min(1.0, float(volume_level)))
        cmd.extend(["volume", f"{target:.2f}"])
    else:
        return ToolResult(
            tool_name="control_music",
            success=False,
            error=f"Unsupported media action '{action}'.",
        )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
        if proc.returncode == 0:
            logger.info("music_control_executed", action=clean_act, player=player)
            return ToolResult(
                tool_name="control_music",
                success=True,
                data={"action": clean_act, "player": player, "volume_level": volume_level},
                display_text=f"🎵 Media action '{clean_act}' executed successfully.",
            )
        else:
            err = proc.stderr.strip() or "No active media players found."
            logger.info("music_control_no_player", error=err)
            return ToolResult(
                tool_name="control_music",
                success=False,
                error=err,
                display_text=f"Media control: {err}",
            )
    except Exception as exc:
        logger.exception("music_control_failed", error=str(exc))
        return ToolResult(
            tool_name="control_music",
            success=False,
            error=str(exc),
        )


def get_current_track() -> ToolResult:
    """
    Query currently playing track metadata via playerctl.
    """
    if not shutil.which("playerctl"):
        return ToolResult(
            tool_name="get_current_track",
            success=False,
            error="playerctl is not installed on this system.",
        )

    try:
        # Check status
        status_proc = subprocess.run(
            ["playerctl", "status"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        if status_proc.returncode != 0:
            return ToolResult(
                tool_name="get_current_track",
                success=True,
                data={"status": "stopped", "playing": False},
                display_text="No active media playback detected on any player.",
            )

        status = status_proc.stdout.strip()

        # Query metadata with formatted string
        meta_proc = subprocess.run(
            [
                "playerctl",
                "metadata",
                "--format",
                "{{playerName}}|{{status}}|{{artist}}|{{title}}|{{album}}",
            ],
            capture_output=True,
            text=True,
            timeout=3.0,
        )

        output = meta_proc.stdout.strip()
        parts = output.split("|") if output else []
        player = parts[0] if len(parts) > 0 else "unknown"
        playback_state = parts[1] if len(parts) > 1 else status
        artist = parts[2] if len(parts) > 2 and parts[2] else "Unknown Artist"
        title = parts[3] if len(parts) > 3 and parts[3] else "Unknown Track"
        album = parts[4] if len(parts) > 4 and parts[4] else "Unknown Album"

        data = {
            "player": player,
            "status": playback_state,
            "artist": artist,
            "title": title,
            "album": album,
            "playing": playback_state.lower() == "playing",
        }

        display = f"🎶 Now Playing on {player} ({playback_state}):\n• **Title:** {title}\n• **Artist:** {artist}\n• **Album:** {album}"
        return ToolResult(
            tool_name="get_current_track",
            success=True,
            data=data,
            display_text=display,
        )

    except Exception as exc:
        logger.exception("get_current_track_failed", error=str(exc))
        return ToolResult(
            tool_name="get_current_track",
            success=False,
            error=str(exc),
        )


def _find_audio_files(query: str | None, search_dirs: list[Path]) -> list[Path]:
    """Find matching audio files under given search directories."""
    matches: list[Path] = []
    clean_q = (query or "").lower().strip()

    for directory in search_dirs:
        if not directory.exists():
            continue
        try:
            for root, _, files in os.walk(directory):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in MUSIC_EXTENSIONS:
                        path = Path(root) / f
                        if not clean_q or clean_q in f.lower() or clean_q in str(path).lower():
                            matches.append(path)
        except Exception as exc:
            logger.warning("music_search_dir_error", dir=str(directory), error=str(exc))

    return matches


def play_local_music(
    query: str | None = None,
    file_path: str | None = None,
) -> ToolResult:
    """
    Search and play a local audio file or song in ~/Music using headless mpv.
    """
    if not shutil.which("mpv"):
        return ToolResult(
            tool_name="play_local_music",
            success=False,
            error="mpv is not installed on this system. Please install mpv.",
        )

    target_file: Path | None = None

    if file_path:
        p = Path(os.path.expanduser(file_path)).resolve()
        if p.exists() and p.is_file():
            target_file = p
        else:
            return ToolResult(
                tool_name="play_local_music",
                success=False,
                error=f"File not found: {file_path}",
            )

    if not target_file:
        home_music = Path.home() / "Music"
        home_downloads = Path.home() / "Downloads"
        cwd = Path.cwd()
        matches = _find_audio_files(query, [home_music, home_downloads, cwd])

        if not matches:
            hint = f" matching '{query}'" if query else ""
            return ToolResult(
                tool_name="play_local_music",
                success=False,
                error=f"No local audio files{hint} found in ~/Music.",
                display_text=f"No local audio files{hint} found in ~/Music. Would you like me to play it on YouTube instead?",
            )
        target_file = matches[0]

    try:
        # Spawn mpv headlessly with MPRIS support enabled
        cmd = ["mpv", "--no-video", str(target_file)]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("mpv_playback_started", file=str(target_file))
        return ToolResult(
            tool_name="play_local_music",
            success=True,
            data={"file_path": str(target_file), "filename": target_file.name},
            display_text=f"▶️ Now playing local track: **{target_file.name}** via MPV.",
        )
    except Exception as exc:
        logger.exception("play_local_music_failed", error=str(exc))
        return ToolResult(
            tool_name="play_local_music",
            success=False,
            error=f"Failed to launch MPV: {exc}",
        )

