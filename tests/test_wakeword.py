"""
tests/test_wakeword.py

Unit tests for Phase 2: Hands-Free Wake Word, VAD, and Acoustic Chime System.
"""

import io
import wave
import numpy as np
import pytest

from voice.wakeword.chime import (
    generate_activation_chime,
    generate_acknowledgment_chime,
    to_wav_bytes,
)
from voice.wakeword.detector import CHUNK_SAMPLES, SAMPLE_RATE, WakeWordDetector
from voice.wakeword.listener import HandsFreeVoiceListener
from voice.wakeword.vad import VoiceActivityDetector


class TestAcousticChime:
    """Tests for chime synthesis and audio buffer conversion."""

    def test_activation_chime_generation(self) -> None:
        chime = generate_activation_chime(sample_rate=16000)
        assert isinstance(chime, np.ndarray)
        assert chime.dtype == np.int16
        assert len(chime) > 0
        # Check volume scaling avoids clipping (-32768 to 32767)
        assert np.max(chime) <= 32767
        assert np.min(chime) >= -32768

    def test_acknowledgment_chime_generation(self) -> None:
        chime = generate_acknowledgment_chime(sample_rate=16000)
        assert isinstance(chime, np.ndarray)
        assert chime.dtype == np.int16
        assert len(chime) > 0

    def test_to_wav_bytes_creates_valid_wav(self) -> None:
        chime = generate_activation_chime(sample_rate=16000)
        wav_bytes = to_wav_bytes(chime, sample_rate=16000)

        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) > 44  # Standard WAV header is 44 bytes

        # Validate with python's wave module
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == len(chime)


class TestVoiceActivityDetector:
    """Tests for RMS and VAD silence end-pointing."""

    def setup_method(self) -> None:
        self.vad = VoiceActivityDetector(sample_rate=16000, energy_threshold=0.02)

    def test_rms_calculation(self) -> None:
        silence = np.zeros(1280, dtype=np.int16)
        assert self.vad.calculate_rms(silence) == 0.0

        signal = (np.ones(1280, dtype=np.int16) * 10000)
        rms = self.vad.calculate_rms(signal)
        assert rms > 0.1

    def test_noise_floor_calibration(self) -> None:
        ambient_frames = [
            (np.random.randn(1280) * 100).astype(np.int16)
            for _ in range(5)
        ]
        self.vad.calibrate(ambient_frames)
        assert self.vad._noise_floor > 0
        assert self.vad.energy_threshold > self.vad._noise_floor

    def test_is_speech_detection(self) -> None:
        silence = np.zeros(1280, dtype=np.int16)
        assert self.vad.is_speech(silence) is False

        # Strong speech signal
        loud_speech = (np.random.randn(1280) * 8000).astype(np.int16)
        assert self.vad.is_speech(loud_speech) is True


class TestWakeWordDetector:
    """Tests for continuous wake word detector engine."""

    def test_detector_initialization(self) -> None:
        detector = WakeWordDetector()
        assert detector.threshold == 0.5
        assert "hey_jarvis" in detector.wake_words
        assert "hey_nyx" in detector.wake_words
        assert detector.vad is not None

    def test_process_silent_frame_returns_none(self) -> None:
        detector = WakeWordDetector()
        silent_frame = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
        result = detector.process_frame(silent_frame)
        assert result is None

    def test_process_variable_length_frame(self) -> None:
        detector = WakeWordDetector()
        # Shorter frame (e.g. 1000 samples instead of 1280)
        short_frame = np.zeros(1000, dtype=np.int16)
        result = detector.process_frame(short_frame)
        assert result is None

        # Longer frame
        long_frame = np.zeros(2000, dtype=np.int16)
        result = detector.process_frame(long_frame)
        assert result is None


class TestHandsFreeVoiceListener:
    """Tests for the hands-free voice listener container."""

    def test_listener_initialization(self) -> None:
        listener = HandsFreeVoiceListener(sample_rate=16000, pause_threshold_seconds=0.8)
        assert listener._sample_rate == 16000
        assert listener._pause_threshold == 0.8
        assert listener.detector is not None
        assert listener.vad is not None

    def test_to_wav_bytes(self) -> None:
        listener = HandsFreeVoiceListener(sample_rate=16000)
        audio = np.zeros(16000, dtype=np.int16)  # 1 second of silence
        wav_bytes = listener._to_wav_bytes(audio)

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getnframes() == 16000

