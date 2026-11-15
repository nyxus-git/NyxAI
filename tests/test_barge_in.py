"""
tests/test_barge_in.py

Unit tests for NyxAI Conversational Duplex Voice and Barge-In (Interruptibility).
"""

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voice.tts.speaker import (
    cancel_current_playback,
    is_playback_active,
    play_audio_array,
    play_wav_bytes,
)


def test_is_playback_active_initially_false() -> None:
    assert is_playback_active() is False


def test_cancel_playback_when_idle_returns_false() -> None:
    assert cancel_current_playback() is False


@patch("sounddevice.play")
@patch("sounddevice.stop")
def test_play_audio_array_interrupted(mock_sd_stop: MagicMock, mock_sd_play: MagicMock) -> None:
    sample_rate = 16000
    # 2 seconds of silence
    dummy_samples = np.zeros(sample_rate * 2, dtype=np.float32)

    def interrupt_worker():
        time.sleep(0.08)
        assert is_playback_active() is True
        cancelled = cancel_current_playback()
        assert cancelled is True

    thread = threading.Thread(target=interrupt_worker)
    thread.start()

    start_t = time.time()
    res = play_audio_array(dummy_samples, sample_rate=sample_rate, interruptible=True)
    elapsed = time.time() - start_t
    thread.join()

    # Should have returned False due to interruption
    assert res is False
    # Should have terminated well before 2 seconds
    assert elapsed < 1.0
    assert is_playback_active() is False
    mock_sd_stop.assert_called()


@patch("sounddevice.play")
@patch("sounddevice.stop")
def test_play_audio_array_runs_to_completion(mock_sd_stop: MagicMock, mock_sd_play: MagicMock) -> None:
    sample_rate = 16000
    # Very short audio (0.05s)
    dummy_samples = np.zeros(int(sample_rate * 0.05), dtype=np.float32)

    res = play_audio_array(dummy_samples, sample_rate=sample_rate, interruptible=True)
    assert res is True
    assert is_playback_active() is False
    mock_sd_stop.assert_not_called()

