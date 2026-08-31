"""
api/app/schemas/chat.py

Pydantic schemas for the /chat endpoint.

These define the API contract for text-based conversation.
The schemas are intentionally kept simple for Phase 1 and will be
extended in Phase 5 (memory) and Phase 6 (agent mode).
"""

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
            "In Phase 1, conversation history is in-memory only."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Hello NyxAI! आज काय plan आहे?",
                "conversation_id": None,
            }
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

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "अरे, मी NyxAI! आज सगळं ठीक आहे. तुझ्याशी बोलायला मजा येते! 😊",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                "model": "qwen2.5:3b",
            }
        }
    }
