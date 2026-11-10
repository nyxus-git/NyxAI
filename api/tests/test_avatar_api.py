"""
api/tests/test_avatar_api.py

Tests for Avatar API routes (/avatar/config, /avatar/photo, /avatar/model)
and emotion + viseme payloads on /chat.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.routers import avatar as avatar_router
from api.app.routers import voice as voice_router
from api.app.services.avatar_service import AvatarConfig
from voice.stt.transcriber import TranscriptionResult
from voice.tts.speaker import _float32_to_wav_bytes


@pytest.fixture
def avatar_client(tmp_path: Path) -> TestClient:
    """Isolated TestClient for /avatar endpoints backed by a temporary assets dir."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    config_path = assets_dir / "avatar_config.json"

    app = FastAPI()
    app.include_router(avatar_router.router)

    with (
        patch.object(avatar_router, "AVATAR_ASSETS_DIR", assets_dir),
        patch("api.app.services.avatar_service.AVATAR_ASSETS_DIR", assets_dir),
        patch("api.app.services.avatar_service.AVATAR_CONFIG_PATH", config_path),
    ):
        yield TestClient(app)


class TestAvatarApi:
    """Validate avatar configuration, photo upload, and model upload endpoints."""

    def test_get_default_avatar_config(self, avatar_client: TestClient) -> None:
        resp = avatar_client.get("/avatar/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "stylized"
        assert data["name"] == "Nyx"
        assert data["voice"] == "af_heart"
        assert "landmarks" in data
        assert len(data["available_voices"]) >= 1

    def test_update_avatar_config_persists(self, avatar_client: TestClient) -> None:
        cfg = AvatarConfig(name="Aria", voice="af_bella", mode="stylized").model_dump()
        post_resp = avatar_client.post("/avatar/config", json=cfg)
        assert post_resp.status_code == 200
        assert post_resp.json()["name"] == "Aria"
        assert post_resp.json()["voice"] == "af_bella"

        get_resp = avatar_client.get("/avatar/config")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Aria"

    def test_upload_and_delete_photo(self, avatar_client: TestClient) -> None:
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        resp = avatar_client.post(
            "/avatar/photo",
            files={"file": ("girl.png", fake_png, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "photo"
        assert data["photo_url"].startswith("/avatar/assets/custom_avatar.png")

        del_resp = avatar_client.delete("/avatar/photo")
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["photo_url"] is None
        assert del_data["mode"] == "stylized"

    def test_reject_invalid_photo_extension(self, avatar_client: TestClient) -> None:
        resp = avatar_client.post(
            "/avatar/photo",
            files={"file": ("script.exe", b"MZ", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_upload_vrm_model(self, avatar_client: TestClient) -> None:
        resp = avatar_client.post(
            "/avatar/model",
            files={"file": ("companion.vrm", b"glTF" + b"\x00" * 24, "model/gltf-binary")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "vrm"
        assert data["model_url"].startswith("/avatar/assets/custom_model.vrm")


class TestChatVisemesAndEmotion:
    """Validate chat endpoint returns emotion and timed visemes when TTS is present."""

    def test_chat_includes_emotion_and_visemes(self, test_client: TestClient) -> None:
        class FakeSpeaker:
            def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
                t = np.linspace(0, 0.25, 4000, endpoint=False)
                samples = (0.35 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
                return _float32_to_wav_bytes(samples, 16000)

        test_client.app.state.tts_speaker = FakeSpeaker()  # type: ignore[union-attr]
        resp = test_client.post("/chat", json={"message": "Say hi!", "tts": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio"]
        assert isinstance(data["visemes"], list)
        assert len(data["visemes"]) > 0
        assert "mouth_open" in data["visemes"][0]
        assert "viseme" in data["visemes"][0]
        assert data["emotion"] in {
            "idle",
            "happy",
            "excited",
            "confused",
            "concerned",
        }


class TestVoiceAskEndpoint:
    """Validate HTTP /voice/ask fallback and WebSocket voice pipeline."""

    def test_voice_ask_processes_wav_audio(self, test_client: TestClient) -> None:
        import base64

        class FakeTranscriber:
            def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
                assert audio_bytes[:4] == b"RIFF"
                return TranscriptionResult(text="Hello Nyx", language="en", language_probability=0.98)

        class FakeSpeaker:
            def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
                t = np.linspace(0, 0.2, 3200, endpoint=False)
                return _float32_to_wav_bytes((0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), 16000)

        test_client.app.include_router(voice_router.router)  # type: ignore[union-attr]
        test_client.app.state.transcriber = FakeTranscriber()  # type: ignore[union-attr]
        test_client.app.state.tts_speaker = FakeSpeaker()  # type: ignore[union-attr]

        fake_wav = _float32_to_wav_bytes(np.zeros(1600, dtype=np.float32), 16000)
        b64 = base64.b64encode(fake_wav).decode()

        resp = test_client.post("/voice/ask", json={"data": b64, "mode": "companion"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcript"] == "Hello Nyx"
        assert data["text"]
        assert data["audio"]
        assert len(data["visemes"]) > 0

    def test_agent_confirm_executes_tool(self, test_client: TestClient, monkeypatch) -> None:
        import shutil
        import subprocess
        from core.agent.tool_registry import ToolRegistry
        from tools.files.file_tools import OPEN_APPLICATION_DEF, open_application

        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/firefox" if name == "firefox" else None)
        launched = []
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))

        reg = ToolRegistry()
        reg.register(OPEN_APPLICATION_DEF, open_application)
        test_client.app.state.tool_registry = reg  # type: ignore[union-attr]
        test_client.app.state.tts_speaker = None  # type: ignore[union-attr]

        resp = test_client.post(
            "/agent/confirm",
            json={"tool_name": "open_application", "arguments": {"application": "firefox"}, "tts": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_used"] == "open_application"
        assert data["tool_result"]["launched"] is True
        assert launched == [["firefox"]]

