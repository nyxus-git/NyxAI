"""
tests/test_chimes.py

Unit tests for acoustic sci-fi feedback chime generation and playback.
Verifies pure mathematical synthesis across all chime modes:
activation, acknowledgment, success, warning, error.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from voice.wakeword.chime import (
    generate_acknowledgment_chime,
    generate_activation_chime,
    generate_error_chime,
    generate_success_chime,
    generate_warning_chime,
    play_chime,
    to_wav_bytes,
)


class TestChimeSynthesis:
    """Tests for waveform generation of acoustic sci-fi feedback tones."""

    def test_activation_chime_waveform(self) -> None:
        audio = generate_activation_chime(sample_rate=16000)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.int16
        # Duration: ~200ms -> ~3200 samples
        assert 3000 <= len(audio) <= 3500
        assert np.max(np.abs(audio)) > 1000  # Non-silent

    def test_acknowledgment_chime_waveform(self) -> None:
        audio = generate_acknowledgment_chime(sample_rate=16000)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.int16
        assert 2500 <= len(audio) <= 3200

    def test_success_chime_waveform(self) -> None:
        audio = generate_success_chime(sample_rate=16000)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.int16
        # Duration: ~240ms -> ~3840 samples
        assert 3500 <= len(audio) <= 4200

    def test_warning_chime_waveform(self) -> None:
        audio = generate_warning_chime(sample_rate=16000)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.int16
        # Duration: ~220ms -> ~3520 samples
        assert 3200 <= len(audio) <= 4000

    def test_error_chime_waveform(self) -> None:
        audio = generate_error_chime(sample_rate=16000)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.int16
        assert 2500 <= len(audio) <= 3200

    def test_to_wav_bytes(self) -> None:
        audio = generate_activation_chime(sample_rate=16000)
        wav = to_wav_bytes(audio, sample_rate=16000)
        assert isinstance(wav, bytes)
        assert wav.startswith(b"RIFF")
        assert b"WAVE" in wav[:16]

    @pytest.mark.parametrize(
        "chime_type",
        ["activation", "acknowledgment", "success", "warning", "error", "unknown_fallback"],
    )
    def test_play_chime_dispatch(self, chime_type: str) -> None:
        with patch("sounddevice.play") as mock_play:
            play_chime(chime_type, sample_rate=16000, async_play=True)
            assert mock_play.called
            args = mock_play.call_args[0]
            assert isinstance(args[0], np.ndarray)

