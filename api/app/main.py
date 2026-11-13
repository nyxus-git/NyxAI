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
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
import aiosqlite

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.app.config import get_settings
from api.app.routers import avatar as avatar_router
from api.app.routers import chat, health
from api.app.routers import memory as memory_router
from api.app.routers import system as system_router
from api.app.routers import voice as voice_router
from api.app.services.avatar_service import ensure_avatar_assets_dir
from api.app.services.chat_service import ChatService
from core.agent.agent import NyxAgent
from core.agent.supervisor import NyxSupervisor
from core.agent.tool_registry import build_default_registry
from core.brain.providers.ollama import OllamaProvider
from core.logging import configure_logging, get_logger
from core.memory import MemoryService
from core.memory.database import MemoryDatabase
from voice.stt.transcriber import WhisperTranscriber
from voice.tts.speaker import NyxTTSSpeaker


async def reminder_poller(db_path: str = "./data/nyx_memory.db") -> None:
    """Background task to poll for due reminders."""
    logger = get_logger(__name__)
    while True:
        try:
            if os.path.exists(db_path):
                now = datetime.now(timezone.utc).isoformat()
                async with aiosqlite.connect(db_path) as conn:
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
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("reminder_poller_error", error=str(e))
        
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break


async def _warmup_pipeline(app: FastAPI) -> None:
    """Pre-load Ollama, Whisper STT, and Kokoro TTS in the background on startup."""
    logger = get_logger(__name__)
    loop = asyncio.get_running_loop()
    try:
        llm = getattr(app.state, "llm_provider", None)
        transcriber = getattr(app.state, "transcriber", None)
        tts_speaker = getattr(app.state, "tts_speaker", None)

        tasks = []
        if llm is not None and hasattr(llm, "warmup"):
            tasks.append(llm.warmup())
        if transcriber is not None and hasattr(transcriber, "_load_model"):
            tasks.append(loop.run_in_executor(None, transcriber._load_model))
        if tts_speaker is not None and hasattr(tts_speaker, "_kokoro"):
            tasks.append(loop.run_in_executor(None, tts_speaker._kokoro._load_model))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("nyxai_warmup_complete")
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("nyxai_warmup_error", error=str(exc))


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

    # Step 5: Build tool registry, agent, and multi-agent supervisor
    logger.info("agent_init", message="Building tool registry, NyxAgent, and NyxSupervisor...")
    tool_registry = build_default_registry()
    base_agent = NyxAgent(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
    )
    supervisor = NyxSupervisor(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        base_agent=base_agent,
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

    # Step 7: Initialize ChatService (now memory-aware and multi-agent orchestrated)
    chat_service = ChatService(
        llm_provider=llm_provider,
        memory_service=memory_service,
        agent=supervisor,
    )

    # Step 8: Store on app.state (accessible in all route handlers)
    app.state.settings = settings
    app.state.llm_provider = llm_provider
    app.state.memory_db = memory_db
    app.state.memory_service = memory_service
    app.state.chat_service = chat_service
    app.state.agent = supervisor
    app.state.base_agent = base_agent
    app.state.supervisor = supervisor
    app.state.tool_registry = tool_registry
    app.state.transcriber = transcriber
    app.state.tts_speaker = tts_speaker

    logger.info("nyxai_ready", message="NyxAI backend is ready to receive requests.")

    # Start background tasks (reminder poller + non-blocking model warmup)
    poller_task = asyncio.create_task(reminder_poller(settings.memory_db_path))
    warmup_task = asyncio.create_task(_warmup_pipeline(app))

    yield  # ← Application runs here

    # Shutdown
    logger.info("nyxai_shutting_down")
    warmup_task.cancel()
    poller_task.cancel()
    try:
        await asyncio.gather(warmup_task, poller_task, return_exceptions=True)
    except Exception:
        pass
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
    app.include_router(avatar_router.router)
    app.include_router(system_router.router)

    # Serve uploaded/custom avatar assets
    avatar_assets_dir = ensure_avatar_assets_dir()
    app.mount(
        "/avatar/assets",
        StaticFiles(directory=str(avatar_assets_dir)),
        name="avatar-assets",
    )

    # Serve built Companion UI when available (enables 1-server desktop app mode)
    project_root = Path(__file__).resolve().parents[2]
    ui_dist_dir = project_root / "apps" / "companion" / "dist"
    ui_index_file = ui_dist_dir / "index.html"

    if ui_dist_dir.is_dir():
        assets_dir = ui_dist_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="ui-assets",
        )
        mediapipe_dir = ui_dist_dir / "mediapipe"
        if mediapipe_dir.is_dir():
            app.mount(
                "/mediapipe",
                StaticFiles(directory=str(mediapipe_dir)),
                name="ui-mediapipe",
            )

    @app.get("/", include_in_schema=False)
    async def root():
        if ui_index_file.is_file():
            return FileResponse(
                ui_index_file,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
            )
        return RedirectResponse(url="/docs")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        fav = ui_dist_dir / "favicon.svg"
        if fav.is_file():
            return FileResponse(fav)
        return RedirectResponse(url="/docs")

    return app


app = create_app()
