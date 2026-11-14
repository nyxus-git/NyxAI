"""
voice/tts/speaker.py

Text-to-Speech system for NyxAI.

Architecture:
  - TTSProvider: Abstract base class — same pattern as LLMProvider/STTProvider.
  - KokoroSpeaker: High-quality English TTS using kokoro-onnx (MIT licensed).
    Runs on CPU via ONNX — no GPU needed (Whisper uses the GPU).
  - Pyttsx3Speaker: Offline fallback for Hindi and Marathi using pyttsx3 + eSpeak-NG.
  - NyxTTSSpeaker: Smart router — picks the best provider based on detected language.

Language routing:
  - English ('en')        → KokoroSpeaker (natural, high quality)
  - Hindi ('hi')          → Pyttsx3Speaker (offline, eSpeak-NG)
  - Marathi ('mr')        → Pyttsx3Speaker (offline, eSpeak-NG)
  - Other / Unknown       → KokoroSpeaker (fallback)

Usage:
    speaker = NyxTTSSpeaker(voice="af_heart", speed=1.0)
    speaker.speak("Hello! How are you?", language="en")
    audio_bytes = speaker.synthesize("नमस्ते!", language="hi")
"""

from __future__ import annotations

import io
import os
import re
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)

# Languages routed to the pyttsx3 fallback (eSpeak-NG)
_PYTTSX3_LANGUAGES = {"hi", "mr", "pa", "bn", "gu", "te", "ta", "kn"}
_MITHI_LANGUAGES = {"hi", "mr", "pa", "bn", "gu", "te", "ta", "kn", "ml", "or"}


def clean_tts_text(text: str) -> str:
    """
    Clean text for text-to-speech engines:
    - Removes markdown formatting (code blocks, backticks, bold, italic, links, headers).
    - Removes URLs and emoji characters.
    - Normalizes consecutive whitespace.
    """
    if not text:
        return ""
    # Remove code blocks
    t = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    t = re.sub(r"`([^`]+)`", r"\1", t)
    # Remove markdown links: [label](url) -> label
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    # Remove raw URLs
    t = re.sub(r"https?://\S+", "", t)
    # Remove markdown headers (#, ##, etc.)
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.MULTILINE)
    # Remove markdown bold/italic (**text**, *text*, __text__, _text_)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = re.sub(r"_([^_]+)_", r"\1", t)
    # Remove blockquotes and list bullets at line starts
    t = re.sub(r"^[\s>*+-]+\s*", "", t, flags=re.MULTILINE)
    # Remove emojis (surrogates and broad Unicode symbol blocks)
    t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
    # Normalize whitespaces
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Abstract Provider


class TTSProvider(ABC):
    """
    Abstract base class for NyxAI text-to-speech providers.

    All TTS implementations must satisfy this interface so they are
    interchangeable. The same `speak()` / `synthesize()` API regardless
    of which engine is underneath.
    """

    @abstractmethod
    def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        """
        Convert text to speech and return WAV audio bytes.

        Args:
            text: The text to synthesize.
            language: Language code ('en', 'hi', 'mr', etc.).
            voice: Optional voice ID override.

        Returns:
            WAV audio as bytes (16-bit PCM, 24kHz or 22kHz depending on engine).
        """
        ...

    @abstractmethod
    def speak(self, text: str, language: str = "en") -> None:
        """
        Synthesize text and play it through the default audio output.

        Blocks until playback is complete.

        Args:
            text: The text to speak.
            language: Language code.
        """
        ...

    @abstractmethod
    def get_engine_name(self) -> str:
        """Return the TTS engine identifier."""
        ...


# Kokoro TTS (English — High Quality)


class KokoroSpeaker(TTSProvider):
    """
    High-quality English TTS using kokoro-onnx.

    kokoro-onnx is a state-of-the-art TTS system based on the Kokoro model.
    It runs on CPU via ONNX Runtime — no GPU required.
    MIT licensed. No cloud calls. ~82M parameter model.

    Voices available (examples):
      - af_heart  : warm, natural American female
      - af_nova   : clear, professional American female
      - am_adam   : natural American male
      - bf_emma   : British female
      - bm_george : British male

    Args:
        voice: Kokoro voice name. Default: 'af_heart'.
        speed: Speech speed multiplier. 1.0 = normal, 1.2 = slightly faster.
    """

    def __init__(self, voice: str = "af_heart", speed: float = 1.0) -> None:
        self._voice = voice
        self._speed = speed
        self._kokoro: Any = None  # Lazy-loaded on first call
        self._fallback: Pyttsx3Speaker | None = None
        self._lock = threading.Lock()

        logger.info("kokoro_tts_configured", voice=voice, speed=speed)

    def _load_model(self) -> None:
        """Load the Kokoro ONNX model (lazy init, thread-safe)."""
        if self._kokoro is not None or self._fallback is not None:
            return

        with self._lock:
            if self._kokoro is not None or self._fallback is not None:  # Double-check after acquiring lock
                return

            logger.info(
                "kokoro_model_loading",
                message="Loading Kokoro TTS model (~82M params, CPU/ONNX)...",
            )
            try:
                import os
                import urllib.request
                from kokoro_onnx import Kokoro

                cache_dir = os.path.expanduser("~/.cache/kokoro")
                os.makedirs(cache_dir, exist_ok=True)

                model_path = os.path.join(cache_dir, "kokoro-v1.0.onnx")
                voices_path = os.path.join(cache_dir, "voices-v1.0.bin")

                if not os.path.exists(model_path):
                    logger.info("kokoro_downloading_model", message="Downloading kokoro-v1.0.onnx (~86MB)...")
                    urllib.request.urlretrieve(
                        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
                        model_path,
                    )

                if not os.path.exists(voices_path):
                    logger.info("kokoro_downloading_voices", message="Downloading voices-v1.0.bin (~28MB)...")
                    urllib.request.urlretrieve(
                        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                        voices_path,
                    )

                self._kokoro = Kokoro(model_path, voices_path)
                logger.info("kokoro_model_loaded")

            except Exception as e:
                logger.error("kokoro_model_load_failed", error=str(e), message="Falling back to pyttsx3 TTS")
                self._fallback = Pyttsx3Speaker()
                self._kokoro = None

    def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        """
        Synthesize text to WAV bytes using Kokoro.

        Args:
            text: Text to synthesize (English recommended for best quality).
            language: Language code (Kokoro works best with 'en').
            voice: Optional Kokoro voice ID override.

        Returns:
            WAV audio bytes (24kHz, 16-bit, mono).
        """
        self._load_model()

        if self._fallback is not None:
            return self._fallback.synthesize(text, language)

        if not text.strip():
            return b""

        selected_voice = voice or self._voice
        logger.debug("kokoro_synthesizing", text_preview=text[:60], voice=selected_voice)

        try:
            if self._kokoro is None:
                raise RuntimeError("Kokoro model not loaded")

            # Kokoro returns: (audio_samples: np.ndarray[float32], sample_rate: int)
            samples, sample_rate = self._kokoro.create(
                text,
                voice=selected_voice,
                speed=self._speed,
                lang="en-us",
            )

            # Convert float32 samples to 16-bit PCM WAV bytes
            wav_bytes = _float32_to_wav_bytes(samples, sample_rate)

            logger.info(
                "kokoro_synthesis_complete",
                text_preview=text[:60],
                duration_s=round(len(samples) / sample_rate, 2),
            )
            return wav_bytes

        except Exception as e:
            logger.error("kokoro_synthesis_error", error=str(e), text_preview=text[:60])
            if self._fallback is None:
                self._fallback = Pyttsx3Speaker()
            return self._fallback.synthesize(text, language)

    def speak(self, text: str, language: str = "en") -> None:
        """
        Synthesize text and play through the default audio output.

        Uses sounddevice for playback — works with PulseAudio/PipeWire.
        Blocks until playback is complete.
        """
        if not text.strip():
            return

        self._load_model()

        if self._fallback is not None:
            self._fallback.speak(text, language)
            return

        try:
            import sounddevice as sd

            if self._kokoro is None:
                raise RuntimeError("Kokoro model not loaded")

            samples, sample_rate = self._kokoro.create(
                text,
                voice=self._voice,
                speed=self._speed,
                lang="en-us",
            )

            logger.info("kokoro_speaking", text_preview=text[:60], sample_rate=sample_rate)
            sd.play(samples, samplerate=sample_rate)
            sd.wait()  # Block until audio finishes
            logger.debug("kokoro_speaking_done")

        except Exception as e:
            logger.error("kokoro_speak_error", error=str(e))
            if self._fallback is None:
                self._fallback = Pyttsx3Speaker()
            self._fallback.speak(text, language)

    def get_engine_name(self) -> str:
        return f"kokoro/{self._voice}"


# Pyttsx3 TTS (Hindi/Marathi Fallback)


class Pyttsx3Speaker(TTSProvider):
    """
    Offline TTS using pyttsx3 + eSpeak-NG for Indian language support.

    pyttsx3 is a text-to-speech conversion library in Python.
    On Linux, it uses eSpeak-NG which supports Hindi, Marathi, and many
    other languages. Lower quality than Kokoro but fully offline and multilingual.

    Args:
        speed: Words per minute. Default 150 = natural pace.
        voice_id: Optional specific eSpeak voice ID (e.g., 'hi' for Hindi).
    """

    def __init__(self, speed: int = 150, voice_id: str | None = None) -> None:
        self._speed = speed
        self._voice_id = voice_id
        self._engine: Any = None
        self._lock = threading.Lock()

        logger.info("pyttsx3_tts_configured", speed=speed)

    def _get_engine(self) -> Any:
        """Deprecated: We no longer hold an engine in-process."""
        return None

    def _get_lang_candidates(self, language: str) -> list[str]:
        """Return priority-ordered eSpeak voice ID candidates for the language.

        eSpeak-NG voice naming is inconsistent across distros. We try multiple
        known IDs in order so that at least one matches on Arch/EndeavourOS.

        Args:
            language: Language code ('hi', 'mr', 'en', etc.)

        Returns:
            List of candidate voice IDs to try, in priority order.
        """
        candidates: dict[str, list[str]] = {
            "hi":  ["hi", "hi-in", "hindi"],                   # Hindi
            "mr":  ["mr", "mb-mr1", "mr-in", "marathi", "hi"], # Marathi (fallback to Hindi)
            "en":  ["en-us", "en", "english"],                  # English
            "pa":  ["pa", "punjabi"],                           # Punjabi
            "bn":  ["bn", "bengali"],                           # Bengali
            "gu":  ["gu", "gujarati"],                          # Gujarati
            "ta":  ["ta", "tamil"],                             # Tamil
            "te":  ["te", "telugu"],                            # Telugu
        }
        return candidates.get(language, ["en-us"])

    def synthesize(self, text: str, language: str = "hi", voice: str | None = None) -> bytes:
        """
        Synthesize text to WAV bytes using pyttsx3.

        Note: pyttsx3 saves to a temp file then reads back.
        This is less efficient than Kokoro's direct array output but
        works reliably for all eSpeak-supported languages.

        Returns:
            WAV audio bytes.
        """
        if not text.strip():
            return b""

        import subprocess
        import sys
        import base64
        import tempfile
        import os

        # Base64 encode the text to safely pass it to the python subprocess
        encoded_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        # Build candidate list: voice_id override first, then language candidates
        if self._voice_id:
            candidates = [self._voice_id] + self._get_lang_candidates(language)
        else:
            candidates = self._get_lang_candidates(language)

        # Serialize candidates as a Python list literal for embedding in the script
        candidates_repr = repr(candidates)

        script = f"""
import pyttsx3
import base64
text = base64.b64decode('{encoded_text}').decode('utf-8')
engine = pyttsx3.init()
engine.setProperty('rate', {self._speed})

candidates = {candidates_repr}
all_voices = engine.getProperty('voices')
selected_voice = None

for candidate in candidates:
    candidate_lower = candidate.lower()
    for voice in all_voices:
        vid = str(getattr(voice, 'id', '')).lower()
        vname = str(getattr(voice, 'name', '')).lower()
        if candidate_lower in vid or candidate_lower in vname:
            engine.setProperty('voice', voice.id)
            selected_voice = voice.id
            break
    if selected_voice:
        break

import sys
if selected_voice:
    print(f'[pyttsx3] Using voice: {{selected_voice}}', file=sys.stderr)
else:
    print(f'[pyttsx3] WARNING: No matching voice found for candidates {{candidates}}', file=sys.stderr)

engine.save_to_file(text, '{tmp_path}')
engine.runAndWait()
"""
        try:
            # Run in isolated subprocess to avoid libespeak C-level conflict
            proc = subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
            )
            # Log the voice selection result from subprocess stderr
            if proc.stderr:
                stderr_msg = proc.stderr.decode("utf-8", errors="ignore").strip()
                if stderr_msg:
                    logger.debug("pyttsx3_subprocess_stderr", message=stderr_msg)

            with open(tmp_path, "rb") as f:
                return f.read()
        except subprocess.CalledProcessError as e:
            logger.error("pyttsx3_subprocess_failed", error=e.stderr.decode("utf-8", errors="ignore"))
            return b""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def speak(self, text: str, language: str = "hi") -> None:
        """
        Speak text aloud using pyttsx3 (blocks until complete).
        Synthesizes audio via isolated subprocess and plays via sounddevice.
        """
        if not text.strip():
            return

        logger.info("pyttsx3_speaking", text_preview=text[:60], language=language)
        try:
            wav_bytes = self.synthesize(text, language)
            if not wav_bytes:
                logger.warning("pyttsx3_synthesis_returned_empty")
                return

            import io
            import wave
            import numpy as np
            import sounddevice as sd

            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sample_rate = wf.getframerate()
                raw_bytes = wf.readframes(wf.getnframes())
                audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0

            sd.play(audio_float32, samplerate=sample_rate)
            sd.wait()
            logger.debug("pyttsx3_speaking_done")
        except Exception as e:
            logger.warning("pyttsx3_speaking_failed", error=str(e), hint="Ensure espeak-ng and sounddevice are installed")

    def get_engine_name(self) -> str:
        return "pyttsx3/espeak-ng"


# High-Quality Neural Female Speaker (Hindi, Marathi, English)


class EdgeTTSSpeaker(TTSProvider):
    """
    High-fidelity Neural Female TTS provider using Edge-TTS.
    Provides human-like, warm female voices for Hindi, Marathi, and English.
    """

    VOICE_MAP = {
        "hi": "hi-IN-SwaraNeural",
        "mr": "mr-IN-AarohiNeural",
        "en-in": "en-IN-NeerjaExpressiveNeural",
        "en": "en-IN-NeerjaExpressiveNeural",
        "pa": "pa-IN-OjasNeural",
        "bn": "bn-IN-TanishaaNeural",
        "gu": "gu-IN-DhwaniNeural",
        "ta": "ta-IN-PallaviNeural",
        "te": "te-IN-ShrutiNeural",
        "kn": "kn-IN-SapnaNeural",
        "ml": "ml-IN-SobhanaNeural",
    }

    def __init__(self, fallback: TTSProvider | None = None) -> None:
        self._fallback = fallback

    def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        clean_text = clean_tts_text(text)
        if not clean_text:
            return b""

        import asyncio
        import concurrent.futures
        import io
        import edge_tts
        import soundfile as sf

        if voice and (voice in self.VOICE_MAP.values() or "Neural" in voice):
            target_voice = voice
        else:
            default_voice = self.VOICE_MAP.get("hi" if language == "hi" else "en", "hi-IN-SwaraNeural")
            target_voice = self.VOICE_MAP.get(language.lower()) or default_voice

        async def _run_edge() -> bytes:
            communicate = edge_tts.Communicate(clean_text, target_voice)
            mp3_bytes = b""
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    chunk_data = chunk.get("data")
                    if isinstance(chunk_data, bytes):
                        mp3_bytes += chunk_data
            if not mp3_bytes:
                return b""
            data, sr = sf.read(io.BytesIO(mp3_bytes))
            return _float32_to_wav_bytes(data, sr)

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(_run_edge())).result(timeout=12.0)
            else:
                return asyncio.run(_run_edge())
        except Exception as e:
            logger.warning("edge_tts_failed_fallback", error=str(e), language=language)
            if self._fallback:
                return self._fallback.synthesize(text, language=language, voice=voice)
            return b""

    def speak(self, text: str, language: str = "en") -> None:
        wav = self.synthesize(text, language=language)
        if wav:
            play_wav_bytes(wav)
        elif self._fallback:
            self._fallback.speak(text, language=language)

    def get_engine_name(self) -> str:
        return "edge-tts/neural-female"


# Mithi TTS (Authentic Indian Female Voices — Oomni/mithi-v2-flash)


class MithiSpeaker(TTSProvider):
    """
    High-fidelity neural TTS using Oomni/mithi-v2-flash.
    Provides natural, human-like Indian female voices (Charvi, Ahana, Vaidehi, Malini, Jahnavi)
    and male voices (Satvik, Anirban, Nakul, Vasant, Siddhant) for 11 Indian languages + English.

    Voices available:
      Female:
        - charvi  : Warm, natural, friendly Indian female voice (default)
        - ahana   : Clear, expressive Indian female voice
        - vaidehi : Soft, polite Indian female voice
        - malini  : Articulate, poised Indian female voice
        - jahnavi : Bright, energetic Indian female voice
      Male:
        - satvik, anirban, nakul, vasant, siddhant

    Supported languages:
      hi (Hindi), mr (Marathi), en (English), bn (Bengali), gu (Gujarati),
      kn (Kannada), ml (Malayalam), or (Odia), pa (Punjabi), ta (Tamil), te (Telugu)

    Args:
        voice: Default voice name (default: 'charvi').
        speed: Speech speed multiplier.
        model_dir: Path to mithi-v2-flash directory.
        device: 'cuda' or 'cpu' (defaults to 'cuda' if torch.cuda.is_available() else 'cpu').
        fallback: Optional fallback TTSProvider if Mithi is unavailable.
    """

    FEMALE_VOICES = ("charvi", "ahana", "vaidehi", "malini", "jahnavi")
    MALE_VOICES = ("satvik", "anirban", "nakul", "vasant", "siddhant")
    ALL_VOICES = FEMALE_VOICES + MALE_VOICES
    LANGUAGES = {"hi", "mr", "en", "bn", "gu", "kn", "ml", "or", "pa", "ta", "te"}

    def __init__(
        self,
        voice: str = "charvi",
        speed: float = 1.0,
        model_dir: str | Path | None = None,
        device: str | None = None,
        fallback: TTSProvider | None = None,
    ) -> None:
        self._voice = voice if voice in self.ALL_VOICES else "charvi"
        self._speed = speed
        self._fallback = fallback
        self._lock = threading.Lock()
        self._mithi: Any = None
        self._sr: int = 24000

        if model_dir is not None:
            self._model_dir = Path(model_dir)
        else:
            project_root = Path(__file__).resolve().parent.parent.parent
            self._model_dir = project_root / "models" / "tts" / "mithi-v2-flash"

        self._device = device
        logger.info(
            "mithi_tts_configured",
            voice=self._voice,
            model_dir=str(self._model_dir),
            device=self._device,
        )

    def _load_model(self) -> None:
        """Lazy load the Mithi model into GPU/CPU memory with auto-CPU fallback on low VRAM."""
        if self._mithi is not None:
            return

        with self._lock:
            if self._mithi is not None:
                return

            if not self._model_dir.exists() or not (self._model_dir / "run.py").exists():
                logger.warning(
                    "mithi_model_not_found",
                    path=str(self._model_dir),
                    hint="Model not downloaded yet. Falling back.",
                )
                if self._fallback is None:
                    self._fallback = EdgeTTSSpeaker(fallback=Pyttsx3Speaker())
                return

            try:
                import importlib.util
                import torch

                # Smart device selection: ensure at least 500MB free VRAM before attempting CUDA
                chosen_device = self._device
                if not chosen_device:
                    if torch.cuda.is_available():
                        try:
                            free_b, total_b = torch.cuda.mem_get_info()
                            if free_b >= 500 * 1024 * 1024:
                                chosen_device = "cuda"
                            else:
                                logger.info(
                                    "mithi_using_cpu_low_vram",
                                    free_mb=round(free_b / 1024 / 1024, 1),
                                    message="GPU VRAM is tight (<500MB free). Running Mithi on CPU for stable synthesis.",
                                )
                                chosen_device = "cpu"
                        except Exception:
                            chosen_device = "cpu"
                    else:
                        chosen_device = "cpu"

                logger.info(
                    "mithi_model_loading",
                    path=str(self._model_dir),
                    device=chosen_device,
                )

                run_path = str(self._model_dir / "run.py")
                spec = importlib.util.spec_from_file_location("mithi_flash_tts", run_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Cannot load module spec from {run_path}")

                mithi_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mithi_mod)
                self._mithi_mod = mithi_mod

                try:
                    self._mithi = mithi_mod.Mithi(
                        model_dir=str(self._model_dir),
                        device=chosen_device,
                    )
                except Exception as cuda_err:
                    if chosen_device == "cuda":
                        logger.warning("mithi_cuda_init_failed_trying_cpu", error=str(cuda_err))
                        torch.cuda.empty_cache()
                        chosen_device = "cpu"
                        self._mithi = mithi_mod.Mithi(
                            model_dir=str(self._model_dir),
                            device="cpu",
                        )
                    else:
                        raise cuda_err

                self._current_device = chosen_device
                self._sr = getattr(mithi_mod, "SR", 24000)
                logger.info(
                    "mithi_model_loaded_successfully",
                    device=chosen_device,
                    sample_rate=self._sr,
                    voices=self._mithi.voices,
                )
            except Exception as e:
                logger.error("mithi_model_load_failed", error=str(e))
                if self._fallback is None:
                    self._fallback = EdgeTTSSpeaker(fallback=Pyttsx3Speaker())

    def _normalize_lang(self, language: str) -> str:
        """Normalize language tags (e.g. 'hi-IN', 'hin', 'mr', 'en-US') to Mithi codes."""
        lang_clean = language.strip().lower().split("-")[0].split("_")[0]
        if lang_clean in self.LANGUAGES:
            return lang_clean
        mapping = {
            "hin": "hi",
            "mar": "mr",
            "eng": "en",
            "ben": "bn",
            "guj": "gu",
            "kan": "kn",
            "mal": "ml",
            "ori": "or",
            "pan": "pa",
            "tam": "ta",
            "tel": "te",
        }
        return mapping.get(lang_clean, "hi")

    def synthesize(self, text: str, language: str = "hi", voice: str | None = None) -> bytes:
        clean_text = clean_tts_text(text)
        if not clean_text:
            return b""

        self._load_model()

        if self._mithi is None:
            if self._fallback:
                return self._fallback.synthesize(clean_text, language=language, voice=voice)
            return b""

        target_lang = self._normalize_lang(language)
        target_voice = voice or self._voice
        if target_voice not in self.ALL_VOICES:
            target_voice = self._voice

        try:
            audio_samples = self._mithi.synthesize(
                clean_text,
                lang=target_lang,
                voice=target_voice,
            )
            return _float32_to_wav_bytes(audio_samples, self._sr)
        except Exception as e:
            # If CUDA throws OOM during inference, reload on CPU and retry once
            if getattr(self, "_current_device", None) == "cuda" and ("CUDA" in str(e) or "out of memory" in str(e).lower()):
                try:
                    import torch
                    torch.cuda.empty_cache()
                    logger.warning("mithi_cuda_oom_retrying_on_cpu", error=str(e))
                    if hasattr(self, "_mithi_mod"):
                        self._mithi = self._mithi_mod.Mithi(model_dir=str(self._model_dir), device="cpu")
                        self._current_device = "cpu"
                        audio_samples = self._mithi.synthesize(
                            clean_text,
                            lang=target_lang,
                            voice=target_voice,
                        )
                        return _float32_to_wav_bytes(audio_samples, self._sr)
                except Exception as cpu_err:
                    logger.error("mithi_cpu_retry_failed", error=str(cpu_err))

            logger.warning("mithi_synthesis_failed_fallback", error=str(e), text=clean_text[:50])
            if self._fallback:
                return self._fallback.synthesize(clean_text, language=language, voice=voice)
            return b""

    def speak(self, text: str, language: str = "hi") -> None:
        clean_text = clean_tts_text(text)
        if not clean_text:
            return

        wav = self.synthesize(clean_text, language=language)
        if wav:
            play_wav_bytes(wav)
        elif self._fallback:
            self._fallback.speak(clean_text, language=language)

    def get_engine_name(self) -> str:
        return f"mithi/{self._voice}"


# Smart Router — NyxTTSSpeaker


class NyxTTSSpeaker(TTSProvider):
    """
    The main TTS provider for NyxAI.

    Automatically routes to the best available TTS engine based on language:
      - When use_mithi=True (default):
          Routes Indian languages ('hi', 'mr', 'pa', 'bn', etc.) and optionally English
          to MithiSpeaker (Oomni/mithi-v2-flash) with authentic Indian female voices
          ('charvi', 'ahana', 'vaidehi', etc.).
      - Fallback: EdgeTTSSpeaker (Swara/Aarohi neural female voice).
      - English fallback: KokoroSpeaker (af_heart natural female).
      - Fully offline fallback: Pyttsx3Speaker (eSpeak-NG).

    Args:
        kokoro_voice: Kokoro voice name for English TTS.
        tts_speed: Speech speed multiplier (applies to Kokoro).
        use_edge_neural: Whether to route Hindi/Marathi to neural female voices.
        use_mithi: Whether to use Mithi for Indian languages.
        mithi_voice: Mithi female voice name ('charvi', 'ahana', 'vaidehi', 'malini', 'jahnavi').
        prefer_mithi_for_english: Whether to use Mithi's Indian voice for English too.
    """

    def __init__(
        self,
        kokoro_voice: str = "af_heart",
        tts_speed: float = 1.0,
        use_edge_neural: bool = True,
        use_mithi: bool = True,
        mithi_voice: str = "charvi",
        prefer_mithi_for_english: bool = False,
    ) -> None:
        self._kokoro = KokoroSpeaker(voice=kokoro_voice, speed=tts_speed)
        self._pyttsx3 = Pyttsx3Speaker()
        self._use_edge = use_edge_neural
        self._edge_tts = EdgeTTSSpeaker(fallback=self._pyttsx3)
        self._use_mithi = use_mithi
        self._mithi_voice = mithi_voice
        self._prefer_mithi_for_english = prefer_mithi_for_english
        self._mithi = MithiSpeaker(
            voice=mithi_voice,
            fallback=self._edge_tts if use_edge_neural else self._pyttsx3,
        )

        logger.info(
            "nyx_tts_speaker_initialized",
            kokoro_voice=kokoro_voice,
            speed=tts_speed,
            use_edge_neural=use_edge_neural,
            use_mithi=use_mithi,
            mithi_voice=mithi_voice,
            prefer_mithi_for_english=prefer_mithi_for_english,
        )

    def _get_provider(self, language: str) -> TTSProvider:
        """Select the appropriate TTS provider for the given language."""
        lang_base = language.strip().lower().split("-")[0].split("_")[0]

        # 1. Primary: Mithi Indian neural female speaker
        if getattr(self, "_use_mithi", False) and getattr(self, "_mithi", None) is not None:
            if lang_base in _PYTTSX3_LANGUAGES or lang_base in _MITHI_LANGUAGES:
                return self._mithi
            if lang_base == "en" and getattr(self, "_prefer_mithi_for_english", False):
                return self._mithi

        # 2. Secondary fallback: Edge TTS neural female voice
        if getattr(self, "_use_edge", False) and lang_base in _PYTTSX3_LANGUAGES:
            return self._edge_tts

        # 3. pyttsx3 fallback
        if lang_base in _PYTTSX3_LANGUAGES:
            return self._pyttsx3

        # 4. Kokoro for English or general fallback
        return self._kokoro

    def synthesize(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        """
        Synthesize text to WAV bytes, routing to the best engine for the language.

        Args:
            text: Text to synthesize.
            language: Language code from Whisper detection ('en', 'hi', 'mr', etc.).
            voice: Optional voice ID override (used for Kokoro/Mithi).

        Returns:
            WAV audio bytes.
        """
        provider = self._get_provider(language)
        logger.debug(
            "nyx_tts_routing",
            language=language,
            engine=provider.get_engine_name(),
            voice=voice,
        )
        return provider.synthesize(text, language=language, voice=voice)

    def speak(self, text: str, language: str = "en") -> None:
        """
        Speak text aloud, routing to the best engine for the language.

        Blocks until playback completes.
        """
        provider = self._get_provider(language)
        provider.speak(text, language=language)

    def get_engine_name(self) -> str:
        return "nyx-tts-router"


# Utility


def _float32_to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """
    Convert a float32 audio numpy array to WAV file bytes.

    Args:
        samples: Float32 audio samples in range [-1.0, 1.0].
        sample_rate: Sample rate in Hz.

    Returns:
        WAV file content as bytes (16-bit PCM).
    """
    # Clip to prevent clipping distortion
    samples = np.clip(samples, -1.0, 1.0)
    # Convert float32 → int16
    int16_samples = (samples * 32767).astype(np.int16)

    buf = io.BytesIO()
    with io.BytesIO() as buf:
        import wave
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)          # Mono
            wf.setsampwidth(2)          # 16-bit = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(int16_samples.tobytes())
        return buf.getvalue()


def play_wav_bytes(wav_bytes: bytes) -> None:
    """
    Play WAV audio bytes through the default audio output.

    Convenience function for playing pre-synthesized audio.

    Args:
        wav_bytes: WAV file bytes to play.
    """
    import io
    import wave

    import sounddevice as sd

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        raw_frames = wf.readframes(wf.getnframes())
        int16_data = np.frombuffer(raw_frames, dtype=np.int16)
        float32_data = int16_data.astype(np.float32) / 32768.0

    sd.play(float32_data, samplerate=sample_rate)
    sd.wait()
