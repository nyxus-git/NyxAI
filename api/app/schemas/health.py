"""
api/app/schemas/health.py

Pydantic schemas for the /health endpoint.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str = Field(description="Service status. 'healthy' or 'degraded'.")
    version: str = Field(description="Application version string.")
    model: str = Field(description="Currently configured LLM model name.")
    ollama_connected: bool = Field(
        description="Whether Ollama is reachable and the model is available."
    )

    model_config = {"json_schema_extra": {"example": {
        "status": "healthy",
        "version": "0.1.0",
        "model": "qwen2.5:3b",
        "ollama_connected": True,
    }}}
