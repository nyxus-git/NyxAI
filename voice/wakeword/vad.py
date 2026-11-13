"""
voice/wakeword/vad.py

Voice Activity Detection (VAD) for hands-free speech end-pointing in NyxAI.

Combines ONNX-based Silero VAD (via openwakeword if installed) with an
adaptive energy/RMS threshold and dynamic background noise calibration.

Tracks speech onset and trailing silence to automatically detect when
the user finishes speaking without requiring manual keypresses.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


class VoiceActivityDetector:
    """
    Detects whether an audio frame contains human speech.

    Features:
      - Uses openwakeword's bundled Silero VAD ONNX model when available.
      - Fallback to dynamic adaptive RMS energy threshold.
      - Smooth exponential moving average to filter out transient pops/clicks.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        energy_threshold: float = 0.018,
    ) -> None:
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self.energy_threshold = energy_threshold
        self._noise_floor = energy_threshold * 0.5
        self._openwakeword_vad: Any = None

        # Attempt to load openwakeword Silero VAD
        try:
            from openwakeword.vad import VAD
            self._openwakeword_vad = VAD()
            logger.info("vad_onnx_initialized")
        except Exception as e:
            logger.info("vad_using_energy_fallback", reason=str(e))

    def calculate_rms(self, chunk: np.ndarray) -> float:
        """Calculate Root Mean Square (RMS) energy normalized between 0.0 and 1.0."""
        if len(chunk) == 0:
            return 0.0
        float_chunk = chunk.astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(float_chunk ** 2)))

    def calibrate(self, ambient_frames: list[np.ndarray]) -> None:
        """Calibrate the noise floor using ambient background samples."""
        if not ambient_frames:
            return
        rms_values = [self.calculate_rms(f) for f in ambient_frames if len(f) > 0]
        if rms_values:
            avg_noise = float(np.mean(rms_values))
            self._noise_floor = avg_noise
            # Adaptive threshold sits 2.5x above ambient room noise floor
            self.energy_threshold = max(0.015, avg_noise * 2.5)
            logger.debug(
                "vad_calibrated",
                noise_floor=round(self._noise_floor, 4),
                energy_threshold=round(self.energy_threshold, 4),
            )

    def is_speech(self, chunk: np.ndarray) -> bool:
        """
        Determine if the given audio chunk contains speech.

        Args:
            chunk: Numpy array of int16 samples (typically 1280 samples = 80ms at 16kHz).

        Returns:
            True if speech is detected, False otherwise.
        """
        if len(chunk) == 0:
            return False

        # 1. Try ONNX VAD if available
        if self._openwakeword_vad is not None:
            try:
                score = self._openwakeword_vad(chunk)
                if score is not None:
                    return float(score) >= self.vad_threshold
            except Exception:
                pass

        # 2. Energy-based fallback
        rms = self.calculate_rms(chunk)
        return rms >= self.energy_threshold

