"""
api/app/config.py

NyxAI application configuration using Pydantic Settings.

All configuration is read from environment variables or a .env file.
No values are hardcoded — especially the model name.

Usage:
    from api.app.config import get_settings
    settings = get_settings()
    print(settings.ollama_model)  # e.g. "qwen2.5:3b"

The get_settings() function is cached with @lru_cache so the .env file
is only parsed once per process lifetime.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    NyxAI application settings.

    Values are loaded in priority order:
      1. Actual environment variables (highest priority)
      2. Values in .env file
      3. Default values defined here (lowest priority)

    Never hardcode secrets or model names — always use env vars.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars gracefully
    )

    # ─── Application ──────────────────────────────────────────────────────────
    app_name: str = Field(default="NyxAI", description="Application display name")
    app_version: str = Field(default="0.1.0", description="Application version string")
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")

    # ─── API Server ───────────────────────────────────────────────────────────
    host: str = Field(default="127.0.0.1", description="API server bind host")
    port: int = Field(default=8000, description="API server bind port")

    # ─── Ollama LLM ───────────────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL",
    )
    ollama_model: str = Field(
        default="qwen2.5:3b",
        description=(
            "Ollama model name. Never hardcoded — always read from environment. "
            "Recommended for 6GB VRAM: qwen2.5:3b"
        ),
    )
    ollama_timeout: float = Field(
        default=120.0,
        description="Ollama HTTP request timeout in seconds",
    )

    # ─── Conversation ─────────────────────────────────────────────────────────
    max_conversation_tokens: int = Field(
        default=4096,
        description="Maximum tokens to send in conversation context window",
    )
    default_language: str = Field(
        default="auto",
        description="Default response language. 'auto' matches the user's language.",
    )

    # ─── Voice / STT (Phase 3) ────────────────────────────────────────────────
    whisper_model: str = Field(
        default="small",
        description="Whisper model size: tiny, base, small, medium, large-v3. Default: small.",
    )
    whisper_device: str = Field(
        default="cuda",
        description="Device for Whisper inference: 'cuda' or 'cpu'. cuda uses RTX 4050.",
    )
    whisper_compute_type: str = Field(
        default="float16",
        description="Whisper compute type: float16 (CUDA), int8 (CPU). float16 on GPU is fastest.",
    )
    whisper_language: str = Field(
        default="auto",
        description="STT language hint: 'auto' for detection, or 'en', 'hi', 'mr' to force.",
    )

    # ─── Voice / TTS (Phase 3) ────────────────────────────────────────────────
    tts_engine: str = Field(
        default="kokoro",
        description="TTS engine: 'kokoro' (English, high quality) or 'pyttsx3' (multilingual fallback).",
    )
    tts_voice: str = Field(
        default="af_heart",
        description="Kokoro voice name. See kokoro-onnx docs for available voices.",
    )
    tts_speed: float = Field(
        default=1.0,
        description="TTS speech speed multiplier. 1.0 = normal, 1.2 = slightly faster.",
    )

    # ─── Audio Recording (Phase 3) ────────────────────────────────────────────
    audio_sample_rate: int = Field(
        default=16000,
        description="Microphone sample rate in Hz. Whisper expects 16000 Hz.",
    )
    audio_channels: int = Field(
        default=1,
        description="Microphone channels. 1 = mono (required by Whisper).",
    )

    # ─── Validators ───────────────────────────────────────────────────────────
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return upper

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"OLLAMA_BASE_URL must start with http:// or https://. Got: '{v}'")
        return v.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings instance.

    This function is safe to call from anywhere — it only loads and
    validates the configuration once per process.

    Returns:
        Settings instance populated from environment / .env file.
    """
    return Settings()
