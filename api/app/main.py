"""
api/app/main.py

NyxAI FastAPI application entry point.

This module creates and configures the FastAPI application instance.
It is the root of the backend system.

How it works:
  - The `lifespan` context manager runs on startup/shutdown.
  - On startup: settings are loaded, logging is configured, the LLM
    provider is initialized, and the ChatService is created. All shared
    state is stored on `app.state` for injection into route handlers.
  - On shutdown: the HTTP client is cleanly closed.

Running:
    uvicorn api.app.main:app --reload --host 127.0.0.1 --port 8000

Or via Makefile:
    make dev
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.app.config import get_settings
from api.app.routers import chat, health
from api.app.routers import voice as voice_router
from api.app.services.chat_service import ChatService
from core.agent.agent import NyxAgent
from core.agent.tool_registry import build_default_registry
from core.brain.providers.ollama import OllamaProvider
from core.logging import configure_logging, get_logger
from voice.stt.transcriber import WhisperTranscriber
from voice.tts.speaker import NyxTTSSpeaker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application startup and shutdown lifecycle.

    Startup:
      1. Load settings from environment / .env
      2. Configure structured logging
      3. Initialize OllamaProvider (configures HTTP client)
      4. Initialize NyxAgent + ToolRegistry (Phase 2)
      5. Initialize WhisperTranscriber + NyxTTSSpeaker (Phase 3)
      6. Initialize ChatService
      7. Store all on app.state for dependency access in routers

    Shutdown:
      1. Close the Ollama HTTP client gracefully
    """
    settings = get_settings()

    # Step 1: Configure logging before anything else
    configure_logging(log_level=settings.log_level)
    logger = get_logger(__name__)

    logger.info(
        "nyxai_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        host=settings.host,
        port=settings.port,
    )

    # Step 2: Initialize LLM provider
    logger.info(
        "llm_provider_init",
        provider="OllamaProvider",
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )

    llm_provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout,
    )

    # Step 3: Perform initial health check (non-blocking — we warn but don't crash)
    is_healthy = await llm_provider.health_check()
    if is_healthy:
        logger.info("ollama_ready", model=settings.ollama_model)
    else:
        logger.warning(
            "ollama_not_ready",
            model=settings.ollama_model,
            hint=f"Run: ollama pull {settings.ollama_model}",
        )

    # Step 4: Build tool registry + NyxAgent (Phase 2)
    logger.info("agent_init", message="Building tool registry and NyxAgent...")
    tool_registry = build_default_registry()
    agent = NyxAgent(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
    )

    # Step 5: Initialize Voice pipeline (Phase 3)
    logger.info(
        "voice_init",
        whisper_model=settings.whisper_model,
        whisper_device=settings.whisper_device,
        tts_engine=settings.tts_engine,
        tts_voice=settings.tts_voice,
    )
    transcriber = WhisperTranscriber(
        model=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        language=settings.whisper_language,
    )
    tts_speaker = NyxTTSSpeaker(
        kokoro_voice=settings.tts_voice,
        tts_speed=settings.tts_speed,
    )

    # Step 6: Initialize ChatService (with agent)
    chat_service = ChatService(llm_provider=llm_provider, agent=agent)

    # Step 7: Store on app.state (accessible in all route handlers via request.app.state)
    app.state.settings = settings
    app.state.llm_provider = llm_provider
    app.state.chat_service = chat_service
    app.state.agent = agent
    app.state.tool_registry = tool_registry
    app.state.transcriber = transcriber
    app.state.tts_speaker = tts_speaker

    logger.info("nyxai_ready", message="NyxAI backend is ready to receive requests.")

    yield  # ← Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("nyxai_shutting_down")
    await llm_provider.close()
    logger.info("nyxai_stopped")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Returns:
        Configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "NyxAI — Local-first AI companion and intelligent desktop agent for Linux. "
            "Supports English, Hindi, Marathi, and Hinglish."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Allow all origins during development.
    # In production (Phase 8), restrict to the Tauri app origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(voice_router.router)

    # ── Root redirect ─────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Redirect root to API documentation."""
        return RedirectResponse(url="/docs")

    return app


# The FastAPI application instance.
# This is what uvicorn imports: `uvicorn api.app.main:app`
app = create_app()
