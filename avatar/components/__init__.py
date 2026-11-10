"""
avatar/components package initialization.
"""

from avatar.components.lip_sync import LipSyncEngine, LipSyncFrame
from avatar.components.states import AvatarState, AvatarStateManager, infer_emotion_from_text

__all__ = [
    "LipSyncEngine",
    "LipSyncFrame",
    "AvatarState",
    "AvatarStateManager",
    "infer_emotion_from_text",
]
