"""
tests/test_voice.py

Unit tests for the Phase 3 voice pipeline.

Design notes:
  - These tests do NOT load Whisper or Kokoro models (too slow/heavy for unit tests).
  - They test schemas, data models, routing logic, and integration of components
    that can be verified without GPU/model inference.
  - WhisperTranscriber and TTS model loading is tested via lazy-init unit tests.
  - Audio format conversion utilities are tested with real numpy arrays.
"""

import base64
import io
import json
import wave

import numpy as np
import pytest

from voice.stt.transcriber import TranscriptionResult, TranscriptionSegment, WhisperTranscriber
from voice.tts.speaker import (
    NyxTTSSpeaker,
    _float32_to_wav_bytes,
    _PYTTSX3_LANGUAGES,
)


# ─── TranscriptionResult Tests ────────────────────────────────────────────────


class TestTranscriptionResult:
    """Tests for the TranscriptionResult data model."""

    def test_empty_text_is_empty(self):
        result = TranscriptionResult(text="", language="en")
        assert result.is_empty is True

    def test_whitespace_only_is_empty(self):
        result = TranscriptionResult(text="   \n  ", language="en")
        assert result.is_empty is True

    def test_non_empty_text_is_not_empty(self):
        result = TranscriptionResult(text="Hello NyxAI", language="en")
        assert result.is_empty is False

    def test_hindi_text_not_empty(self):
        result = TranscriptionResult(text="नमस्ते", language="hi")
        assert result.is_empty is False

    def test_default_language_probability(self):
        result = TranscriptionResult(text="test", language="en")
        assert result.language_probability == 1.0

    def test_segments_default_empty(self):
        result = TranscriptionResult(text="hello", language="en")
        assert result.segments == []

    def test_with_segments(self):
        seg = TranscriptionSegment(start=0.0, end=1.5, text="Hello")
        result = TranscriptionResult(
            text="Hello",
            language="en",
            segments=[seg],
        )
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hello"
        assert result.segments[0].start == 0.0
        assert result.segments[0].end == 1.5


# ─── WhisperTranscriber Initialization Tests ─────────────────────────────────


class TestWhisperTranscriberInit:
    """Tests that WhisperTranscriber initializes correctly without loading the model."""

    def test_default_initialization(self):
        """Whisper transcriber initializes with defaults without loading model."""
        t = WhisperTranscriber()
        assert t._model is None  # Lazy — not loaded yet
        assert t._model_name == "small"
        assert t._device == "cuda"
        assert t._compute_type == "float16"

    def test_cpu_initialization(self):
        t = WhisperTranscriber(model="tiny", device="cpu", compute_type="int8")
        assert t._model_name == "tiny"
        assert t._device == "cpu"
        assert t._compute_type == "int8"

    def test_auto_language_maps_to_none(self):
        """'auto' language should set _language to None (Whisper auto-detect)."""
        t = WhisperTranscriber(language="auto")
        assert t._language is None

    def test_explicit_language_preserved(self):
        """Explicit language codes should be preserved."""
        t = WhisperTranscriber(language="hi")
        assert t._language == "hi"

    def test_get_model_name(self):
        t = WhisperTranscriber(model="small")
        assert t.get_model_name() == "faster-whisper/small"

    def test_get_model_name_medium(self):
        t = WhisperTranscriber(model="medium")
        assert t.get_model_name() == "faster-whisper/medium"


# ─── Audio Format Tests ───────────────────────────────────────────────────────


class TestAudioConversion:
    """Tests for audio format conversion utilities."""

    def test_float32_to_wav_bytes_returns_bytes(self):
        """Conversion produces non-empty WAV bytes."""
        samples = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        result = _float32_to_wav_bytes(samples, sample_rate=24000)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_wav_bytes_has_riff_header(self):
        """Output WAV bytes should start with RIFF header."""
        samples = np.random.uniform(-0.5, 0.5, 8000).astype(np.float32)
        wav = _float32_to_wav_bytes(samples, sample_rate=16000)
        assert wav[:4] == b"RIFF"

    def test_wav_bytes_parseable(self):
        """Output WAV bytes should be readable by the wave module."""
        samples = np.random.uniform(-0.5, 0.5, 8000).astype(np.float32)
        wav = _float32_to_wav_bytes(samples, sample_rate=16000)

        with wave.open(io.BytesIO(wav), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() == 16000

    def test_clipping_does_not_corrupt(self):
        """Values outside [-1, 1] should be clipped, not cause errors."""
        samples = np.array([2.0, -3.0, 0.5, 1.5], dtype=np.float32)
        wav = _float32_to_wav_bytes(samples, sample_rate=16000)
        assert len(wav) > 0  # Should not raise or return empty

    def test_transcriber_wav_detection(self):
        """WhisperTranscriber should detect WAV header and parse correctly."""
        t = WhisperTranscriber()

        # Create a minimal WAV file
        samples = np.zeros(16000, dtype=np.float32)
        wav_bytes = _float32_to_wav_bytes(samples, sample_rate=16000)

        # Should parse without error (model not loaded — just tests byte parsing logic)
        audio_array, sr = t._audio_bytes_to_numpy(wav_bytes, sample_rate=16000)
        assert sr == 16000
        assert isinstance(audio_array, np.ndarray)
        assert audio_array.dtype == np.float32

    def test_transcriber_raw_pcm_parsing(self):
        """WhisperTranscriber should handle raw int16 PCM bytes."""
        t = WhisperTranscriber()

        # Raw int16 PCM (no WAV header)
        raw_pcm = np.zeros(16000, dtype=np.int16).tobytes()
        audio_array, sr = t._audio_bytes_to_numpy(raw_pcm, sample_rate=16000)
        assert sr == 16000
        assert isinstance(audio_array, np.ndarray)
        assert audio_array.dtype == np.float32


# ─── TTS Language Routing Tests ───────────────────────────────────────────────


class TestNyxTTSSpeakerRouting:
    """Tests for NyxTTSSpeaker language routing logic."""

    def test_hindi_routes_to_pyttsx3(self):
        """Hindi should route to the pyttsx3 provider."""
        speaker = NyxTTSSpeaker.__new__(NyxTTSSpeaker)  # Create without __init__
        speaker._kokoro = object()   # Mock
        speaker._pyttsx3 = object()  # Mock

        provider = NyxTTSSpeaker._get_provider(speaker, "hi")
        assert provider is speaker._pyttsx3

    def test_marathi_routes_to_pyttsx3(self):
        """Marathi should route to the pyttsx3 provider."""
        speaker = NyxTTSSpeaker.__new__(NyxTTSSpeaker)
        speaker._kokoro = object()
        speaker._pyttsx3 = object()

        provider = NyxTTSSpeaker._get_provider(speaker, "mr")
        assert provider is speaker._pyttsx3

    def test_english_routes_to_kokoro(self):
        """English should route to the Kokoro provider."""
        speaker = NyxTTSSpeaker.__new__(NyxTTSSpeaker)
        speaker._kokoro = object()
        speaker._pyttsx3 = object()

        provider = NyxTTSSpeaker._get_provider(speaker, "en")
        assert provider is speaker._kokoro

    def test_unknown_language_routes_to_kokoro(self):
        """Unknown language codes should fall back to Kokoro."""
        speaker = NyxTTSSpeaker.__new__(NyxTTSSpeaker)
        speaker._kokoro = object()
        speaker._pyttsx3 = object()

        provider = NyxTTSSpeaker._get_provider(speaker, "fr")
        assert provider is speaker._kokoro

    def test_pyttsx3_language_set_contents(self):
        """Verify PYTTSX3_LANGUAGES contains expected Indian languages."""
        assert "hi" in _PYTTSX3_LANGUAGES
        assert "mr" in _PYTTSX3_LANGUAGES
        assert "en" not in _PYTTSX3_LANGUAGES
        assert "fr" not in _PYTTSX3_LANGUAGES

    def test_nyx_speaker_engine_name(self):
        """NyxTTSSpeaker should identify as the router."""
        speaker = NyxTTSSpeaker.__new__(NyxTTSSpeaker)
        assert NyxTTSSpeaker.get_engine_name(speaker) == "nyx-tts-router"


# ─── Voice WebSocket Schema Tests ─────────────────────────────────────────────


class TestVoiceSchemas:
    """Tests for WebSocket message schema serialization."""

    def test_voice_transcript_serializes(self):
        from api.app.schemas.voice import VoiceTranscriptMessage
        msg = VoiceTranscriptMessage(text="Hello", language="en", language_probability=0.99)
        data = msg.model_dump()
        assert data["type"] == "transcript"
        assert data["text"] == "Hello"
        assert data["language"] == "en"

    def test_voice_thinking_serializes(self):
        from api.app.schemas.voice import VoiceThinkingMessage
        msg = VoiceThinkingMessage()
        data = msg.model_dump()
        assert data["type"] == "thinking"

    def test_voice_idle_serializes(self):
        from api.app.schemas.voice import VoiceIdleMessage
        msg = VoiceIdleMessage()
        assert msg.model_dump()["type"] == "idle"

    def test_voice_response_with_audio(self):
        from api.app.schemas.voice import VoiceResponseMessage
        # Create fake base64 audio
        fake_wav = _float32_to_wav_bytes(np.zeros(100, dtype=np.float32), 16000)
        audio_b64 = base64.b64encode(fake_wav).decode()

        msg = VoiceResponseMessage(
            text="Your battery is at 78%!",
            audio=audio_b64,
            tool_used="get_battery_status",
        )
        data = msg.model_dump()
        assert data["type"] == "response"
        assert data["text"] == "Your battery is at 78%!"
        assert data["tool_used"] == "get_battery_status"
        assert len(data["audio"]) > 0

    def test_voice_error_serializes(self):
        from api.app.schemas.voice import VoiceErrorMessage
        msg = VoiceErrorMessage(message="STT failed", code="stt_error")
        data = msg.model_dump()
        assert data["type"] == "error"
        assert data["code"] == "stt_error"

    def test_audio_message_default_mode(self):
        from api.app.schemas.voice import VoiceAudioMessage
        msg = VoiceAudioMessage(data="base64data==")
        assert msg.mode == "companion"  # Default mode


# ─── PushToTalkListener Tests ─────────────────────────────────────────────────


class TestPushToTalkListener:
    """Tests for PushToTalkListener (non-interactive parts only)."""

    def test_initialization(self):
        from voice.wakeword.listener import PushToTalkListener
        listener = PushToTalkListener(sample_rate=16000, channels=1)
        assert listener._sample_rate == 16000
        assert listener._channels == 1

    def test_to_wav_bytes(self):
        """_to_wav_bytes should produce valid WAV bytes."""
        from voice.wakeword.listener import PushToTalkListener
        listener = PushToTalkListener()

        # Create fake int16 audio (1 second of silence)
        audio_data = np.zeros((16000, 1), dtype=np.int16)
        wav_bytes = listener._to_wav_bytes(audio_data)

        assert wav_bytes[:4] == b"RIFF"

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getsampwidth() == 2

    def test_to_wav_bytes_with_real_audio(self):
        """Verify WAV output preserves audio length."""
        from voice.wakeword.listener import PushToTalkListener
        listener = PushToTalkListener(sample_rate=16000)

        # 0.5 seconds of audio
        audio_data = np.random.randint(-1000, 1000, (8000, 1), dtype=np.int16)
        wav_bytes = listener._to_wav_bytes(audio_data)

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frame_count = wf.getnframes()
            # 0.5 seconds * 16000 Hz = 8000 frames
            assert abs(frame_count - 8000) < 100  # Allow small tolerance
