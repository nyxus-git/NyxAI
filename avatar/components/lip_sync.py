"""
avatar/components/lip_sync.py

NyxAI Lip Synchronization Engine (PRD Section 18).

Calculates real-time mouth opening values and visemes from audio amplitude:
Audio Amplitude (RMS) -> Attack/Decay Smoothing -> Normalized Mouth Open (0.0 to 1.0) -> Viseme Classification.
"""

from __future__ import annotations

import io
import math
import wave
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class LipSyncFrame:
    """A single frame of lip sync animation."""

    time_seconds: float
    mouth_open: float  # 0.0 (closed) to 1.0 (wide open)
    viseme: str        # 'closed', 'slight', 'open', 'wide'


class LipSyncEngine:
    """
    Analyzes audio amplitude and generates synchronized mouth movement values.
    """

    def __init__(
        self,
        frame_rate: int = 30,
        noise_floor: float = 0.02,
        max_amplitude: float = 0.5,
        attack_decay_ratio: float = 0.6,
    ) -> None:
        self.frame_rate = frame_rate
        self.noise_floor = noise_floor
        self.max_amplitude = max_amplitude
        self.smoothing = attack_decay_ratio
        self._last_mouth_open = 0.0

    def compute_amplitude_rms(self, samples: np.ndarray) -> float:
        """Calculate Root-Mean-Square (RMS) amplitude of audio samples."""
        if len(samples) == 0:
            return 0.0
        rms = math.sqrt(float(np.mean(np.square(samples))))
        return rms

    def amplitude_to_mouth_open(self, amplitude: float) -> float:
        """
        Map audio amplitude to a normalized mouth-open value (0.0 to 1.0)
        with non-linear scaling and attack-decay smoothing.
        """
        if amplitude <= self.noise_floor:
            target = 0.0
        else:
            # Normalize between noise floor and max amplitude
            scaled = (amplitude - self.noise_floor) / max(self.max_amplitude - self.noise_floor, 0.001)
            target = min(max(scaled, 0.0), 1.0)

        # Smooth using exponential moving average
        smoothed = (self.smoothing * self._last_mouth_open) + ((1.0 - self.smoothing) * target)
        self._last_mouth_open = smoothed
        return round(smoothed, 3)

    def classify_viseme(self, mouth_open: float) -> str:
        """Classify normalized mouth open value into viseme shape."""
        if mouth_open < 0.08:
            return "closed"
        elif mouth_open < 0.35:
            return "slight"
        elif mouth_open < 0.70:
            return "open"
        else:
            return "wide"

    def process_wav_bytes(self, wav_bytes: bytes) -> list[LipSyncFrame]:
        """
        Process entire WAV audio byte buffer into a list of timed LipSyncFrames.
        """
        if not wav_bytes or wav_bytes[:4] != b"RIFF":
            return []

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sample_rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
            int16_samples = np.frombuffer(raw, dtype=np.int16)
            float_samples = int16_samples.astype(np.float32) / 32768.0

        samples_per_frame = max(int(sample_rate / self.frame_rate), 1)
        frames: list[LipSyncFrame] = []
        self._last_mouth_open = 0.0

        for i in range(0, len(float_samples), samples_per_frame):
            chunk = float_samples[i : i + samples_per_frame]
            timestamp = round(i / sample_rate, 3)
            rms = self.compute_amplitude_rms(chunk)
            mouth_open = self.amplitude_to_mouth_open(rms)
            viseme = self.classify_viseme(mouth_open)
            frames.append(LipSyncFrame(time_seconds=timestamp, mouth_open=mouth_open, viseme=viseme))

        return frames
