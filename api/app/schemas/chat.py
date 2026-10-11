"""
api/app/schemas/chat.py

Pydantic schemas for the /chat endpoint.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for POST /chat."""

    message: str = Field(
        description="The user's input message. Supports English, Hindi, Marathi, and Hinglish.",
        min_length=1,
        max_length=8192,
    )
    conversation_id: UUID | None = Field(
        default=None,
        description=(
            "Optional conversation UUID for multi-turn context. "
            "If None, a new conversation is started. "
        ),
    )
    mode: Literal["companion", "agent"] = Field(
        default="companion",
        description=(
            "Operating mode. "
            "'companion' — pure conversational AI, no tools. "
            "'agent' — tool-enabled mode; NyxAI can take real actions."
        ),
    )
    tts: bool = Field(
        default=True,
        description="Whether to generate TTS audio in response. Default: True.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Companion mode (default)",
                    "value": {
                        "message": "Hello NyxAI! आज काय plan आहे?",
                        "conversation_id": None,
                        "mode": "companion",
                    },
                },
                {
                    "summary": "Agent mode — battery check",
                    "value": {
                        "message": "What's my battery level?",
                        "conversation_id": None,
                        "mode": "agent",
                    },
                },
                {
                    "summary": "Agent mode — open app",
                    "value": {
                        "message": "VS Code उघड.",
                        "conversation_id": None,
                        "mode": "agent",
                    },
                },
            ]
        }
    }


class ChatResponse(BaseModel):
    """Response schema for POST /chat."""

    response: str = Field(description="NyxAI's reply to the user's message.")
    conversation_id: UUID = Field(
        description=(
            "UUID for this conversation session. "
            "Pass this back in subsequent requests to maintain context."
        )
    )
    model: str = Field(description="The LLM model that generated this response.")
    mode: Literal["companion", "agent"] = Field(
        description="The mode that was used to generate this response."
    )
    tool_used: str | None = Field(
        default=None,
        description=(
            "Name of the tool that was called, if any. "
            "Only set when mode='agent' and a tool was invoked."
        ),
    )
    tool_result: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Raw output data from the tool, if one was called. "
            "Structure varies by tool."
        ),
    )
    audio: str | None = Field(
        default=None,
        description="Base64-encoded WAV audio of NyxAI's speech response.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Companion response",
                    "value": {
                        "response": "अरे, मी NyxAI! आज सगळं ठीक आहे. 😊",
                        "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                        "model": "qwen2.5:3b",
                        "mode": "companion",
                        "tool_used": None,
                        "tool_result": None,
                    },
                },
                {
                    "summary": "Agent response with battery tool",
                    "value": {
                        "response": "Your battery is at 78% and charging! ⚡",
                        "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
                        "model": "qwen2.5:3b",
                        "mode": "agent",
                        "tool_used": "get_battery_status",
                        "tool_result": {
                            "percent": 78.0,
                            "plugged_in": True,
                            "status": "Charging",
                        },
                    },
                },
            ]
        }
    }
