"""
voice/stt/transcriber.py

Speech-to-Text system for NyxAI using faster-whisper.

Architecture:
  - STTProvider: Abstract base class (same pattern as LLMProvider).
  - WhisperTranscriber: Concrete implementation using faster-whisper.
    - Loads on first call (lazy init) — startup is instant.
    - Runs on CUDA (RTX 4050) with float16 for maximum speed.
    - Falls back to CPU with int8 if CUDA is unavailable.
    - Supports English, Hindi, Marathi + auto-detection.

Usage:
    transcriber = WhisperTranscriber(model="small", device="cuda")
    result = transcriber.transcribe(audio_bytes)
    print(result.text)       # "आत्ता किती वाजले?"
    print(result.language)   # "mr"
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class TranscriptionSegment:
    """
    A single time-stamped segment of transcribed speech.

    Attributes:
        start: Segment start time in seconds.
        end: Segment end time in seconds.
        text: Transcribed text for this segment.
    """

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """
    Complete result from a transcription call.

    Attributes:
        text: Full transcribed text (all segments joined).
        language: Detected or forced language code ('en', 'hi', 'mr', etc.).
        language_probability: Confidence score for language detection (0.0–1.0).
        segments: List of time-stamped segments.
        duration_seconds: Total audio duration processed.
    """

    text: str
    language: str
    language_probability: float = 1.0
    segments: list[TranscriptionSegment] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def is_empty(self) -> bool:
        """Return True if no speech was detected."""
        return not self.text.strip()


# ─── Abstract Provider ────────────────────────────────────────────────────────


class STTProvider(ABC):
    """
    Abstract base class for NyxAI speech-to-text providers.

    All STT implementations must implement this interface so they are
    interchangeable. Currently implemented: WhisperTranscriber.
    Future options: whisper.cpp, Vosk, cloud ASR.
    """

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw PCM audio as bytes (16-bit, mono, 16kHz recommended).
                         Also accepts WAV file bytes (with header).
            sample_rate: Sample rate of the audio. Default 16000 Hz (Whisper native).

        Returns:
            TranscriptionResult with text, language, and segments.
        """
        ...

    @abstractmethod
    def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        Transcribe an audio file (WAV, MP3, etc.) to text.

        Args:
            file_path: Path to the audio file.

        Returns:
            TranscriptionResult with text, language, and segments.
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier being used."""
        ...


# ─── Whisper Implementation ───────────────────────────────────────────────────


class WhisperTranscriber(STTProvider):
    """
    Speech-to-text using faster-whisper (CTranslate2 backend).

    faster-whisper is 2–4x faster than OpenAI Whisper with the same accuracy.
    Supports CUDA for GPU acceleration (RTX 4050 = excellent performance).

    Args:
        model: Whisper model size. Options: tiny, base, small, medium, large-v3.
               'small' is the recommended default: fast + accurate multilingual.
        device: 'cuda' for GPU (default), 'cpu' for CPU-only.
        compute_type: 'float16' for CUDA (fast), 'int8' for CPU (memory-efficient).
        language: Language hint. 'auto' for detection, or 'en', 'hi', 'mr'.
    """

    def __init__(
        self,
        model: str = "small",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "auto",
    ) -> None:
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._language = language if language != "auto" else None
        self._model: Any = None  # Lazy-loaded on first call

        logger.info(
            "whisper_transcriber_configured",
            model=model,
            device=device,
            compute_type=compute_type,
            language=language,
        )

    def _load_model(self) -> None:
        """
        Load the faster-whisper model (lazy initialization).

        Called automatically on first transcribe() call.
        Handles CUDA → CPU fallback if GPU is unavailable.
        """
        if self._model is not None:
            return

        logger.info(
            "whisper_model_loading",
            model=self._model_name,
            device=self._device,
            compute_type=self._compute_type,
            message="First call — downloading model if not cached (~460MB for small)...",
        )

        try:
            from faster_whisper import WhisperModel

            # Attempt to preload cublas if present in common locations (e.g. nvidia pip package or ollama)
            import os
            import ctypes
            for lib_dir in [
                "/usr/local/lib/ollama/cuda_v12",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".venv/lib/python3.14/site-packages/nvidia/cublas/lib"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".venv/lib/python3.11/site-packages/nvidia/cublas/lib"),
            ]:
                if os.path.exists(lib_dir):
                    cublas_path = os.path.join(lib_dir, "libcublas.so.12")
                    if os.path.exists(cublas_path):
                        try:
                            ctypes.CDLL(cublas_path, mode=ctypes.RTLD_GLOBAL)
                            logger.debug("whisper_cublas_preloaded", path=cublas_path)
                        except Exception:
                            pass

            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info(
                "whisper_model_loaded",
                model=self._model_name,
                device=self._device,
            )

        except Exception as e:
            if "cuda" in str(e).lower() or "gpu" in str(e).lower() or "cublas" in str(e).lower():
                logger.warning(
                    "whisper_cuda_fallback",
                    error=str(e)[:100],
                    message="CUDA failed to initialize — falling back to CPU with int8",
                )
                from faster_whisper import WhisperModel

                self._device = "cpu"
                self._compute_type = "int8"
                self._model = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type="int8",
                )
                logger.info("whisper_model_loaded_cpu_fallback", model=self._model_name)
            else:
                raise

    def _audio_bytes_to_numpy(
        self, audio_bytes: bytes, sample_rate: int
    ) -> tuple[np.ndarray, int]:
        """
        Convert audio bytes to a float32 numpy array for Whisper.

        Handles:
          1. WAV file bytes (RIFF header)
          2. WebM, OGG, Opus, MP3 browser audio (via ffmpeg conversion)
          3. Raw PCM int16 bytes fallback

        Returns:
            Tuple of (float32 numpy array, sample_rate).
        """
        # 1. Try WAV header
        if audio_bytes[:4] == b"RIFF":
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    actual_sr = wf.getframerate()
                    raw_bytes = wf.readframes(wf.getnframes())
                    audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0
                    return audio_float32, actual_sr
            except Exception as e:
                logger.warning("whisper_wav_parse_error", error=str(e))

        # 2. Try ffmpeg conversion for WebM, OGG, Opus, MP3 from browser MediaRecorder
        import tempfile
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".media", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            cmd = [
                "ffmpeg",
                "-loglevel", "quiet",
                "-y",
                "-i", tmp_path,
                "-f", "f32le",
                "-ac", "1",
                "-ar", "16000",
                "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and len(res.stdout) > 0:
                audio_float32 = np.frombuffer(res.stdout, dtype=np.float32)
                return audio_float32, 16000
        except Exception as e:
            logger.warning("whisper_ffmpeg_convert_error", error=str(e))
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except OSError:
                pass

        # 3. Fallback to raw int16 PCM
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        return audio_float32, sample_rate

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Transcribe audio bytes to text using faster-whisper.

        Args:
            audio_bytes: Raw PCM int16 or WAV bytes. Mono, 16kHz recommended.
            sample_rate: Sample rate (used for raw PCM; ignored for WAV files).

        Returns:
            TranscriptionResult with transcribed text, detected language, and segments.
        """
        self._load_model()

        if self._model is None:
            raise RuntimeError("Whisper model failed to load")

        audio_float32, actual_rate = self._audio_bytes_to_numpy(audio_bytes, sample_rate)

        logger.debug(
            "whisper_transcribing",
            audio_duration_s=round(len(audio_float32) / actual_rate, 2),
            device=self._device,
        )

        try:
            segments_iter, info = self._model.transcribe(
                audio_float32,
                language=self._language,
                beam_size=5,
                vad_filter=True,          # Skip silent parts (VAD built into faster-whisper)
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=200,
                ),
            )
            segments = []
            full_text_parts = []
            for seg in segments_iter:
                segments.append(
                    TranscriptionSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text.strip(),
                    )
                )
                full_text_parts.append(seg.text.strip())

        except Exception as e:
            if self._device == "cuda" and ("cublas" in str(e).lower() or "cuda" in str(e).lower() or "library" in str(e).lower()):
                logger.warning(
                    "whisper_runtime_cuda_error_fallback",
                    error=str(e)[:100],
                    message="CUDA runtime execution failed — falling back to CPU mode",
                )
                from faster_whisper import WhisperModel
                self._device = "cpu"
                self._compute_type = "int8"
                self._model = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type="int8",
                )
                segments_iter, info = self._model.transcribe(
                    audio_float32,
                    language=self._language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=300,
                        speech_pad_ms=200,
                    ),
                )
                segments = []
                full_text_parts = []
                for seg in segments_iter:
                    segments.append(
                        TranscriptionSegment(
                            start=seg.start,
                            end=seg.end,
                            text=seg.text.strip(),
                        )
                    )
                    full_text_parts.append(seg.text.strip())
            else:
                raise

        full_text = " ".join(full_text_parts).strip()
        duration = len(audio_float32) / actual_rate

        logger.info(
            "whisper_transcription_complete",
            language=info.language,
            language_probability=round(info.language_probability, 3),
            text_preview=full_text[:60],
            duration_s=round(duration, 2),
            segment_count=len(segments),
        )

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            language_probability=info.language_probability,
            segments=segments,
            duration_seconds=duration,
        )

    def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        Transcribe an audio file using faster-whisper.

        Args:
            file_path: Path to an audio file (WAV, MP3, FLAC, etc.).
                       ffmpeg is used internally by faster-whisper for format conversion.

        Returns:
            TranscriptionResult with text and language info.
        """
        self._load_model()

        if self._model is None:
            raise RuntimeError("Whisper model failed to load")

        logger.info("whisper_transcribe_file", path=file_path)

        segments_iter, info = self._model.transcribe(
            file_path,
            language=self._language,
            beam_size=5,
            vad_filter=True,
        )

        segments = []
        full_text_parts = []
        for seg in segments_iter:
            segments.append(
                TranscriptionSegment(start=seg.start, end=seg.end, text=seg.text.strip())
            )
            full_text_parts.append(seg.text.strip())

        full_text = " ".join(full_text_parts).strip()

        logger.info(
            "whisper_file_transcription_complete",
            language=info.language,
            text_preview=full_text[:60],
        )

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            language_probability=info.language_probability,
            segments=segments,
        )

    def get_model_name(self) -> str:
        """Return the Whisper model identifier."""
        return f"faster-whisper/{self._model_name}"
