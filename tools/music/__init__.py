"""
tools/music
Linux MPRIS media controller and local music tools for NyxAI.
"""

from tools.music.music_tools import (
    CONTROL_MUSIC_DEF,
    GET_CURRENT_TRACK_DEF,
    PLAY_LOCAL_MUSIC_DEF,
    control_music,
    get_current_track,
    play_local_music,
)

__all__ = [
    "CONTROL_MUSIC_DEF",
    "GET_CURRENT_TRACK_DEF",
    "PLAY_LOCAL_MUSIC_DEF",
    "control_music",
    "get_current_track",
    "play_local_music",
]

