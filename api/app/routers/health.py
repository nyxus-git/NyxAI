"""
api/app/routers/health.py

Health check endpoint for NyxAI.

GET /health

Returns the current status of the NyxAI backend including:
  - Application liveness
  - Ollama connectivity
  - Configured model name

This endpoint is used by:
  - Developers during local testing
  - systemd service health checks 
  - Frontend connection validation 
"""

from fastapi import APIRouter, Request

from api.app.config import get_settings
from api.app.schemas.health import HealthResponse
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description=(
        "Check if the NyxAI backend is running and the configured LLM model is reachable. "
        "Returns 'healthy' when Ollama is connected and the model is available."
    ),
)
async def health_check(request: Request) -> HealthResponse:
    """
    Perform a health check on the NyxAI backend.

    Checks:
    1. The FastAPI application is running (trivially true if this responds).
    2. The Ollama server is reachable at the configured URL.
    3. The configured model is listed in Ollama's available models.

    Returns:
        HealthResponse with status, version, model, and ollama_connected flag.
    """
    settings = get_settings()

    # Access the LLM provider injected into app state during lifespan
    llm_provider = request.app.state.llm_provider
    ollama_connected = await llm_provider.health_check()

    status = "healthy" if ollama_connected else "degraded"

    logger.info(
        "health_check",
        status=status,
        model=settings.ollama_model,
        ollama_connected=ollama_connected,
    )

    return HealthResponse(
        status=status,
        version=settings.app_version,
        model=settings.ollama_model,
        ollama_connected=ollama_connected,
    )
