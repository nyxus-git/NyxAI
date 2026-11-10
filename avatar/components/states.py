"""
avatar/components/states.py

NyxAI Avatar State Machine.

Manages avatar emotional and interaction states:
  - IDLE: Waiting for user input (subtle breathing/blinking)
  - LISTENING: User is speaking (push-to-talk active)
  - THINKING: Model is reasoning or running tools
  - SPEAKING: Avatar TTS audio is playing with lip-sync
  - HAPPY: Positive feedback or task success
  - EXCITED: Fun conversational moments
  - CONFUSED: Ambiguous input or tool failure
  - CONCERNED: Safety violation attempt or system warning
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class AvatarState(str, Enum):
    """Core avatar animation and emotional states."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    HAPPY = "happy"
    EXCITED = "excited"
    CONFUSED = "confused"
    CONCERNED = "concerned"


class AvatarStateManager:
    """Tracks current avatar state and formats client synchronization events."""

    def __init__(self, initial_state: AvatarState = AvatarState.IDLE) -> None:
        self._current_state: AvatarState = initial_state
        self._state_history: list[AvatarState] = [initial_state]

    @property
    def current_state(self) -> AvatarState:
        return self._current_state

    def set_state(self, new_state: AvatarState | str) -> dict[str, Any]:
        """
        Transition avatar to a new state and return the WebSocket event payload.
        """
        if isinstance(new_state, str):
            new_state = AvatarState(new_state.lower())

        self._current_state = new_state
        self._state_history.append(new_state)
        return self.to_event()

    def to_event(self) -> dict[str, Any]:
        """Format as avatar_state event payload."""
        return {
            "event": "avatar_state",
            "state": self._current_state.value,
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_event())


_EXCITED_MARKERS = ("!", "awesome", "amazing", "great news", "woohoo", "yay", "fantastic", "छान", "मस्त")
_HAPPY_MARKERS = ("happy", "glad", "welcome", "sure", "done", "success", "😊", "😄", "🎉", "❤️", "✨")
_CONFUSED_MARKERS = ("sorry", "not sure", "don't know", "unclear", "couldn't find", "cannot", "माहित नाही", "समजलं नाही")
_CONCERNED_MARKERS = ("warning", "error", "failed", "critical", "blocked", "danger", "permission denied", "low battery")


def infer_emotion_from_text(
    text: str,
    tool_used: str | None = None,
    tool_result: dict[str, Any] | None = None,
) -> AvatarState:
    """Infer an expressive AvatarState from reply text and optional tool status."""
    if tool_result and tool_result.get("error"):
        return AvatarState.CONCERNED

    if tool_used == "get_battery_status" and tool_result:
        pct = tool_result.get("percent")
        plugged = tool_result.get("plugged_in")
        if isinstance(pct, (int, float)) and pct <= 15 and not plugged:
            return AvatarState.CONCERNED

    lower = text.lower()
    if any(marker in lower for marker in _CONCERNED_MARKERS):
        return AvatarState.CONCERNED
    if any(marker in lower for marker in _CONFUSED_MARKERS):
        return AvatarState.CONFUSED
    if any(marker in lower for marker in _HAPPY_MARKERS):
        return AvatarState.HAPPY
    if lower.count("!") >= 2 or any(marker in lower for marker in _EXCITED_MARKERS):
        return AvatarState.EXCITED
    return AvatarState.IDLE
