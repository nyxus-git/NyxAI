"""
api/app/main.py

NyxAI FastAPI application entry point.

Creates and configures the FastAPI app. The `lifespan` context manager
handles startup (init DB, LLM, agent, voice, memory) and shutdown
(graceful HTTP client close). All shared state lives on `app.state`.

Run with:
    uvicorn api.app.main:app --reload --host 127.0.0.1 --port 8000
    make dev
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from datetime import datetime, timezone
import aiosqlite

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.app.config import get_settings
from api.app.routers import chat, health
from api.app.routers import memory as memory_router
from api.app.routers import voice as voice_router
from api.app.services.chat_service import ChatService
from core.agent.agent import NyxAgent
from core.agent.tool_registry import build_default_registry
from core.brain.providers.ollama import OllamaProvider
from core.logging import configure_logging, get_logger
from core.memory import MemoryService
from core.memory.database import MemoryDatabase
from voice.stt.transcriber import WhisperTranscriber
from voice.tts.speaker import NyxTTSSpeaker


async def reminder_poller() -> None:
    """Background task to poll for due reminders."""
    logger = get_logger(__name__)
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            async with aiosqlite.connect("./data/nyx_memory.db") as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT id, title FROM reminders WHERE status = 'pending' AND due_at <= ?",
                    (now,)
                )
                rows = await cursor.fetchall()
                for row in rows:
                    logger.info("reminder_triggered", title=row["title"], reminder_id=row["id"])
                    await conn.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (row["id"],))
                
                if rows:
                    await conn.commit()
        except Exception as e:
            logger.error("reminder_poller_error", error=str(e))
        
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown lifecycle.

    Startup: load settings → init memory DB → init LLM → init agent
             → init voice pipeline → init chat service → store on app.state.
    Shutdown: cancel background tasks, close HTTP client.
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

    # Step 2: Initialize memory system
    logger.info(
        "memory_init",
        db_path=settings.memory_db_path,
        semantic_enabled=settings.semantic_memory_enabled,
        long_term_enabled=settings.long_term_memory_enabled,
        episodic_enabled=settings.episodic_memory_enabled,
    )
    memory_db = MemoryDatabase(db_path=settings.memory_db_path)
    await memory_db.initialize()

    memory_service = MemoryService(
        db=memory_db,
        semantic_memory_enabled=settings.semantic_memory_enabled,
        ollama_base_url=settings.ollama_base_url,
        embedding_model=settings.embedding_model,
        chroma_path=settings.chroma_db_path,
        top_k=settings.memory_retrieval_top_k,
        max_history_turns=settings.max_history_turns,
        long_term_enabled=settings.long_term_memory_enabled,
        episodic_enabled=settings.episodic_memory_enabled,
    )
    await memory_service.initialize()

    # Step 3: Initialize LLM provider
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

    # Step 4: Perform initial health check (non-blocking — warn but don't crash)
    is_healthy = await llm_provider.health_check()
    if is_healthy:
        logger.info("ollama_ready", model=settings.ollama_model)
    else:
        logger.warning(
            "ollama_not_ready",
            model=settings.ollama_model,
            hint=f"Run: ollama pull {settings.ollama_model}",
        )

    # Step 5: Build tool registry and agent
    logger.info("agent_init", message="Building tool registry and NyxAgent...")
    tool_registry = build_default_registry()
    agent = NyxAgent(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
    )

    # Step 6: Initialize voice pipeline
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

    # Step 7: Initialize ChatService (now memory-aware)
    chat_service = ChatService(
        llm_provider=llm_provider,
        memory_service=memory_service,
        agent=agent,
    )

    # Step 8: Store on app.state (accessible in all route handlers)
    app.state.settings = settings
    app.state.llm_provider = llm_provider
    app.state.memory_db = memory_db
    app.state.memory_service = memory_service
    app.state.chat_service = chat_service
    app.state.agent = agent
    app.state.tool_registry = tool_registry
    app.state.transcriber = transcriber
    app.state.tts_speaker = tts_speaker

    logger.info("nyxai_ready", message="NyxAI backend is ready to receive requests.")

    # Start background tasks
    poller_task = asyncio.create_task(reminder_poller())

    yield  # ← Application runs here

    # Shutdown
    logger.info("nyxai_shutting_down")
    poller_task.cancel()
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(voice_router.router)
    app.include_router(memory_router.router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
