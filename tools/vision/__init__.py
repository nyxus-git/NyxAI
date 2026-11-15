"""
tools/vision
Desktop vision and screen awareness tools for NyxAI.
"""

from tools.vision.screen_tools import (
    CAPTURE_SCREEN_DEF,
    INSPECT_SCREEN_ERRORS_DEF,
    READ_SCREEN_TEXT_DEF,
    capture_screen,
    inspect_screen_for_errors,
    read_screen_text,
)

__all__ = [
    "CAPTURE_SCREEN_DEF",
    "READ_SCREEN_TEXT_DEF",
    "INSPECT_SCREEN_ERRORS_DEF",
    "capture_screen",
    "read_screen_text",
    "inspect_screen_for_errors",
]
