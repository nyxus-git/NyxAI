"""
voice/wakeword/chime.py

Acoustic feedback chime generator and player for NyxAI.

Synthesizes soft sci-fi chimes using pure mathematical sine waves with
exponential decay — zero external audio files, zero disk dependencies.

Chimes:
  - Activation: Two-tone ascending chime (D5 587Hz -> A5 880Hz) played on wake-word detection
  - Acknowledgment: Two-tone descending chime (A5 880Hz -> E5 659Hz) played on command completion
"""

from __future__ import annotations

import io
import wave
import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


def generate_activation_chime(sample_rate: int = 16000) -> np.ndarray:
    """
    Generate a pleasant, futuristic ascending two-tone activation chime (D5 -> A5).
    Total duration: ~200 ms.
    """
    # Tone 1: 587.33 Hz (80ms)
    t1 = np.linspace(0, 0.08, int(sample_rate * 0.08), endpoint=False)
    tone1 = np.sin(2 * np.pi * 587.33 * t1) * np.exp(-t1 * 20)

    # Tone 2: 880.00 Hz (120ms)
    t2 = np.linspace(0, 0.12, int(sample_rate * 0.12), endpoint=False)
    tone2 = np.sin(2 * np.pi * 880.00 * t2) * np.exp(-t2 * 14)

    chime = np.concatenate([tone1, tone2])
    # Soft volume scaling to prevent clipping
    return (chime * 0.3 * 32767).astype(np.int16)


def generate_acknowledgment_chime(sample_rate: int = 16000) -> np.ndarray:
    """
    Generate a subtle descending completion chime (A5 -> E5).
    Total duration: ~180 ms.
    """
    t1 = np.linspace(0, 0.07, int(sample_rate * 0.07), endpoint=False)
    tone1 = np.sin(2 * np.pi * 880.00 * t1) * np.exp(-t1 * 22)

    t2 = np.linspace(0, 0.11, int(sample_rate * 0.11), endpoint=False)
    tone2 = np.sin(2 * np.pi * 659.25 * t2) * np.exp(-t2 * 16)

    chime = np.concatenate([tone1, tone2])
    return (chime * 0.25 * 32767).astype(np.int16)


def to_wav_bytes(audio_array: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Convert int16 audio array to WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_array.tobytes())
    return buf.getvalue()


def play_chime(chime_type: str = "activation", sample_rate: int = 16000, async_play: bool = True) -> None:
    """
    Play the requested chime through the default sound device.

    Args:
        chime_type: "activation" or "acknowledgment".
        sample_rate: Audio sampling rate (default 16000 Hz).
        async_play: If True, plays without blocking the calling thread.
    """
    try:
        import sounddevice as sd

        if chime_type == "activation":
            audio = generate_activation_chime(sample_rate)
        else:
            audio = generate_acknowledgment_chime(sample_rate)

        sd.play(audio, samplerate=sample_rate)
        if not async_play:
            sd.wait()
    except Exception as e:
        logger.debug("chime_playback_skipped", reason=str(e))

