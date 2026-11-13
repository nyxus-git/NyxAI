"""
voice/wakeword/detector.py

Real-time wake-word detector for NyxAI.

Runs continuous inference over 16 kHz microphone audio chunks using
openWakeWord ONNX models with minimal CPU overhead (~0.5% CPU).

Triggers hands-free activation when the user says:
  - "Hey Nyx"
  - "Hey Jarvis"
"""

from __future__ import annotations

import time
from typing import Any, Callable
import numpy as np

from core.logging import get_logger
from voice.wakeword.vad import VoiceActivityDetector

logger = get_logger(__name__)

# Sample configuration
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz (openWakeWord native frame size)
DEFAULT_THRESHOLD = 0.5


class WakeWordDetector:
    """
    Continuous wake word detector.

    Processes streaming audio frames and fires triggers when acoustic
    confidence exceeds the detection threshold.
    """

    def __init__(
        self,
        wake_words: list[str] | None = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self.wake_words = wake_words or ["hey_jarvis", "hey_nyx"]
        self.threshold = threshold
        self.vad = VoiceActivityDetector(sample_rate=SAMPLE_RATE)
        self._model: Any = None
        self._is_ready = False

        self._init_engine()

    def _init_engine(self) -> None:
        """Initialize the openWakeWord ONNX model engine."""
        try:
            from openwakeword.model import Model

            self._model = Model(
                inference_framework="onnx",
                vad_threshold=0.3,
            )
            self._is_ready = True
            logger.info(
                "wake_word_engine_initialized",
                available_models=list(self._model.models.keys()),
            )
        except Exception as e:
            logger.warning("wake_word_engine_fallback", reason=str(e))
            self._is_ready = False

    def process_frame(self, frame: np.ndarray) -> str | None:
        """
        Process a single 1280-sample (80ms) audio frame.

        Args:
            frame: Numpy int16 array of 1280 samples.

        Returns:
            The triggered wake word name (e.g., 'hey_jarvis', 'hey_nyx') or None.
        """
        if not self._is_ready or self._model is None:
            return None

        if len(frame) != CHUNK_SAMPLES:
            # Reshape or pad if needed
            if len(frame) < CHUNK_SAMPLES:
                frame = np.pad(frame, (0, CHUNK_SAMPLES - len(frame)))
            else:
                frame = frame[:CHUNK_SAMPLES]

        try:
            prediction = self._model.predict(frame)
            # Check for triggers
            for model_name, score in prediction.items():
                if score >= self.threshold:
                    clean_name = model_name.lower().replace(" ", "_")
                    logger.info(
                        "wake_word_triggered",
                        wake_word=clean_name,
                        score=round(float(score), 3),
                    )
                    # Reset prediction buffer after firing
                    self._model.prediction_buffer[model_name].clear()
                    return clean_name
        except Exception as e:
            logger.debug("wake_word_inference_error", error=str(e))

        return None

    def listen_for_wake_word(
        self,
        timeout_seconds: float | None = None,
        on_wake: Callable[[str], None] | None = None,
    ) -> str | None:
        """
        Blocking audio loop that listens to the microphone until a wake word is detected.

        Args:
            timeout_seconds: Optional timeout before returning None.
            on_wake: Optional callback function called with the detected wake word.

        Returns:
            The detected wake word name, or None if timed out.
        """
        import sounddevice as sd

        logger.info("wake_word_listening_started", target_words=self.wake_words)
        detected_word: list[str] = []
        start_time = time.time()

        def audio_callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
            if status:
                logger.debug("audio_input_status", status=str(status))
            if detected_word:
                return

            flat_data = indata.flatten()
            hit = self.process_frame(flat_data)
            if hit:
                detected_word.append(hit)

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SAMPLES,
            callback=audio_callback,
        ):
            while not detected_word:
                if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                    logger.debug("wake_word_timeout_reached")
                    return None
                time.sleep(0.04)

        word = detected_word[0]
        if on_wake:
            on_wake(word)
        return word

