"""
voice/wakeword/listener.py

Push-to-talk microphone listener for NyxAI.

Records audio from the microphone while the user holds a key,
then returns the audio bytes when they release.

In Phase 3, push-to-talk uses simple Enter key press:
  1. User presses Enter → recording starts
  2. User presses Enter again → recording stops
  3. Audio bytes are returned to the voice pipeline

Usage:
    listener = PushToTalkListener(sample_rate=16000)
    audio_bytes = listener.record_until_keypress()
    # ... pass to transcriber
"""

from __future__ import annotations

import io
import wave
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


class PushToTalkListener:
    """
    Records audio from the microphone until the user signals stop.

    Uses sounddevice to capture microphone input as a numpy array,
    then converts to WAV bytes for the STT transcriber.

    Args:
        sample_rate: Sample rate in Hz. Must be 16000 for Whisper compatibility.
        channels: Number of channels. Must be 1 (mono) for Whisper.
        max_duration_seconds: Maximum recording duration before auto-stop.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        max_duration_seconds: float = 60.0,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._max_duration = max_duration_seconds

        logger.info(
            "push_to_talk_listener_configured",
            sample_rate=sample_rate,
            channels=channels,
            max_duration=max_duration_seconds,
        )

    def record_until_keypress(self) -> bytes:
        """
        Record microphone audio until the user presses Enter.

        Blocking call:
          1. Prints instructions to terminal.
          2. Starts recording when user presses Enter.
          3. Stops when user presses Enter again.
          4. Returns WAV bytes of the recorded audio.

        Returns:
            WAV audio bytes (16-bit PCM, mono, 16kHz).
            Returns empty bytes if no audio was captured.
        """
        import sounddevice as sd

        print("\n🎤 Press Enter to start recording...")
        input()  # Wait for first Enter

        recorded_chunks: list[np.ndarray] = []
        stop_event = __import__("threading").Event()

        def audio_callback(indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
            """Called by sounddevice for each audio block."""
            if status:
                logger.warning("audio_callback_status", status=str(status))
            recorded_chunks.append(indata.copy())

        print("🔴 Recording... Press Enter to stop.")

        # Start background recording stream
        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            callback=audio_callback,
        ):
            input()  # Block until second Enter press

        print("⏹️  Recording stopped. Processing...")
        logger.info("recording_stopped", chunks_captured=len(recorded_chunks))

        if not recorded_chunks:
            logger.warning("no_audio_captured")
            return b""

        # Concatenate all chunks into one array
        audio_data = np.concatenate(recorded_chunks, axis=0)
        return self._to_wav_bytes(audio_data)

    def record_timed(self, duration_seconds: float) -> bytes:
        """
        Record microphone audio for a fixed duration.

        Useful for testing the STT pipeline without interactive input.

        Args:
            duration_seconds: How long to record.

        Returns:
            WAV audio bytes.
        """
        import sounddevice as sd

        logger.info("timed_recording_start", duration_s=duration_seconds)
        print(f"🔴 Recording for {duration_seconds:.1f} seconds...")

        audio_data = sd.rec(
            int(duration_seconds * self._sample_rate),
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
        )
        sd.wait()

        print("⏹️  Done.")
        logger.info("timed_recording_complete")
        return self._to_wav_bytes(audio_data)

    def _to_wav_bytes(self, audio_data: np.ndarray) -> bytes:
        """
        Convert a numpy int16 audio array to WAV bytes.

        Args:
            audio_data: Numpy int16 array from sounddevice.

        Returns:
            WAV file content as bytes.
        """
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_data.tobytes())
        wav_bytes = buf.getvalue()
        logger.debug(
            "wav_bytes_created",
            size_bytes=len(wav_bytes),
            duration_s=round(len(audio_data) / self._sample_rate, 2),
        )
        return wav_bytes
