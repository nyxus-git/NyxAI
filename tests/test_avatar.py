"""
tests/test_avatar.py

Unit tests for Avatar state machine and Lip-Sync engine (avatar/components/).
"""

import numpy as np
import pytest

from avatar.components.lip_sync import LipSyncEngine
from avatar.components.states import AvatarState, AvatarStateManager


class TestAvatarStateManager:
    """Validate avatar emotional/lifecycle states."""

    def test_initial_state(self):
        manager = AvatarStateManager()
        assert manager.current_state == AvatarState.IDLE

    def test_state_transition(self):
        manager = AvatarStateManager()
        event = manager.set_state(AvatarState.THINKING)
        assert manager.current_state == AvatarState.THINKING
        assert event == {"event": "avatar_state", "state": "thinking"}

    def test_string_transition(self):
        manager = AvatarStateManager()
        event = manager.set_state("speaking")
        assert manager.current_state == AvatarState.SPEAKING
        assert event["state"] == "speaking"

    def test_json_serialization(self):
        manager = AvatarStateManager()
        manager.set_state(AvatarState.HAPPY)
        json_str = manager.to_json()
        assert '"event": "avatar_state"' in json_str
        assert '"state": "happy"' in json_str


class TestLipSyncEngine:
    """Validate amplitude calculation and viseme mapping."""

    def test_silence_produces_zero(self):
        engine = LipSyncEngine()
        silence = np.zeros(1600, dtype=np.float32)
        rms = engine.compute_amplitude_rms(silence)
        mouth_open = engine.amplitude_to_mouth_open(rms)
        viseme = engine.classify_viseme(mouth_open)

        assert rms == 0.0
        assert mouth_open == 0.0
        assert viseme == "closed"

    def test_loud_signal_produces_mouth_open(self):
        engine = LipSyncEngine(noise_floor=0.02, max_amplitude=0.5)
        # Sine wave amplitude 0.4
        t = np.linspace(0, 1, 1600, endpoint=False)
        loud_signal = 0.4 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        rms = engine.compute_amplitude_rms(loud_signal)
        mouth_open = engine.amplitude_to_mouth_open(rms)
        viseme = engine.classify_viseme(mouth_open)

        assert rms > 0.1
        assert mouth_open > 0.0
        assert viseme in ["open", "wide", "slight"]

    def test_process_wav_bytes_empty(self):
        engine = LipSyncEngine()
        frames = engine.process_wav_bytes(b"")
        assert frames == []
