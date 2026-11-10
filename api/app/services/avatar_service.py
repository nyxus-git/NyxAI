"""
api/app/services/avatar_service.py

Shared helpers for avatar configuration persistence, speech synthesis with
lip-sync viseme extraction, and emotion inference.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from avatar.components.lip_sync import LipSyncEngine
from avatar.components.states import infer_emotion_from_text
from core.brain.language import detect_response_language
from core.logging import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AVATAR_ASSETS_DIR = PROJECT_ROOT / "avatar" / "assets"
AVATAR_CONFIG_PATH = AVATAR_ASSETS_DIR / "avatar_config.json"

AVAILABLE_FEMALE_VOICES: list[dict[str, str]] = [
    {"id": "af_heart", "label": "Heart (Warm, Natural US)"},
    {"id": "af_bella", "label": "Bella (Expressive US)"},
    {"id": "af_nova", "label": "Nova (Clear, Bright US)"},
    {"id": "af_nicole", "label": "Nicole (Soft, Calm US)"},
    {"id": "af_sarah", "label": "Sarah (Friendly US)"},
    {"id": "af_sky", "label": "Sky (Youthful US)"},
    {"id": "bf_emma", "label": "Emma (British Warm)"},
    {"id": "bf_isabella", "label": "Isabella (British Refined)"},
]


class LandmarkPoint(BaseModel):
    """Normalized landmark region in [0, 1] image coordinates."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    rx: float = Field(default=0.06, ge=0.01, le=0.4)
    ry: float = Field(default=0.03, ge=0.005, le=0.4)


class AvatarLandmarks(BaseModel):
    """Eye and mouth regions used to animate a portrait photo at 60 FPS."""

    left_eye: LandmarkPoint = Field(
        default_factory=lambda: LandmarkPoint(x=0.42, y=0.39, rx=0.055, ry=0.024)
    )
    right_eye: LandmarkPoint = Field(
        default_factory=lambda: LandmarkPoint(x=0.58, y=0.39, rx=0.055, ry=0.024)
    )
    mouth: LandmarkPoint = Field(
        default_factory=lambda: LandmarkPoint(x=0.50, y=0.57, rx=0.085, ry=0.032)
    )
    chin_y: float = Field(default=0.71, ge=0.1, le=1.0)


class AvatarConfig(BaseModel):
    """Persisted companion character configuration."""

    mode: Literal["photo", "vrm", "stylized"] = "stylized"
    name: str = Field(default="Nyx", min_length=1, max_length=40)
    tagline: str = Field(default="Local Desktop AI Companion", max_length=80)
    voice: str = Field(default="af_heart")
    photo_url: str | None = None
    model_url: str | None = None
    landmarks: AvatarLandmarks = Field(default_factory=AvatarLandmarks)


def ensure_avatar_assets_dir(assets_dir: Path | None = None) -> Path:
    """Ensure the avatar assets directory exists and return it."""
    target = assets_dir or AVATAR_ASSETS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def load_avatar_config(config_path: Path | None = None) -> AvatarConfig:
    """Load avatar configuration from disk, returning defaults if missing/corrupt."""
    path = config_path or AVATAR_CONFIG_PATH
    if not path.exists():
        return AvatarConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AvatarConfig.model_validate(raw)
    except Exception as exc:
        logger.warning("avatar_config_load_failed", error=str(exc))
        return AvatarConfig()


def save_avatar_config(config: AvatarConfig, config_path: Path | None = None) -> AvatarConfig:
    """Persist avatar configuration to disk."""
    path = config_path or AVATAR_CONFIG_PATH
    ensure_avatar_assets_dir(path.parent)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return config


def _synthesize_call(
    tts_speaker: Any,
    text: str,
    language: str,
    voice: str | None,
) -> bytes:
    """Invoke tts_speaker.synthesize while staying compatible with minimal test doubles."""
    sig = inspect.signature(tts_speaker.synthesize)
    if "voice" in sig.parameters:
        return tts_speaker.synthesize(text, language=language, voice=voice)
    return tts_speaker.synthesize(text, language=language)


async def synthesize_speech_with_visemes(
    tts_speaker: Any,
    text: str,
    voice: str | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Synthesize response audio and compute timed lip-sync viseme frames.

    Returns:
        Tuple of (base64_wav_or_none, list_of_viseme_dicts).
    """
    if tts_speaker is None or not text.strip():
        return None, []

    selected_voice = voice or load_avatar_config().voice
    response_lang = detect_response_language(text)
    loop = asyncio.get_running_loop()

    wav_bytes: bytes = await loop.run_in_executor(
        None,
        lambda: _synthesize_call(tts_speaker, text, response_lang, selected_voice),
    )
    if not wav_bytes:
        return None, []

    frames = await loop.run_in_executor(
        None,
        lambda: LipSyncEngine(frame_rate=30).process_wav_bytes(wav_bytes),
    )
    visemes = [
        {
            "time_seconds": f.time_seconds,
            "mouth_open": f.mouth_open,
            "viseme": f.viseme,
        }
        for f in frames
    ]
    return base64.b64encode(wav_bytes).decode(), visemes


def detect_response_emotion(
    text: str,
    tool_used: str | None = None,
    tool_result: dict[str, Any] | None = None,
) -> str:
    """Return string value of inferred AvatarState emotion."""
    return infer_emotion_from_text(text, tool_used=tool_used, tool_result=tool_result).value

