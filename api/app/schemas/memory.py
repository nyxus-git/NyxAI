"""
api/app/schemas/memory.py

Pydantic request/response schemas for the NyxAI Memory API.

These models are used by the /memory/* router endpoints to
validate incoming requests and serialize outgoing responses.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ─── Long-Term Memory Schemas ─────────────────────────────────────────────────

class AddMemoryRequest(BaseModel):
    """Request body for POST /memory/long-term."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The fact or preference to remember.",
        examples=["User prefers Hinglish responses."],
    )
    source: str = Field(
        default="manual",
        description="Origin of the memory: 'manual', 'auto', or 'conversation'.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for filtering (e.g. ['preference', 'project']).",
    )


class MemoryItem(BaseModel):
    """A single long-term memory record."""

    id: int = Field(..., description="SQLite integer primary key.")
    content: str = Field(..., description="The memory content text.")
    source: str = Field(..., description="Origin of the memory.")
    tags: str = Field(..., description="Comma-separated tag string.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    updated_at: str = Field(..., description="ISO-8601 last-updated timestamp.")


class AddMemoryResponse(BaseModel):
    """Response body for POST /memory/long-term."""

    id: int = Field(..., description="ID of the newly created memory.")
    content: str = Field(..., description="The stored memory content.")
    message: str = Field(default="Memory saved.", description="Status message.")


class MemoryListResponse(BaseModel):
    """Response body for GET /memory/long-term."""

    memories: list[MemoryItem] = Field(default_factory=list)
    total: int = Field(..., description="Total number of memories returned.")


class DeleteMemoryResponse(BaseModel):
    """Response body for DELETE /memory/long-term/{id}."""

    id: int = Field(..., description="ID of the deleted memory.")
    deleted: bool = Field(..., description="True if the memory was found and deleted.")
    message: str = Field(default="Memory deleted.")


# ─── Conversation Schemas ─────────────────────────────────────────────────────

class ConversationSummary(BaseModel):
    """Summary of a stored conversation session."""

    id: str = Field(..., description="UUID string of the conversation.")
    mode: str = Field(..., description="'companion' or 'agent'.")
    title: str | None = Field(None, description="Optional display title.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    updated_at: str = Field(..., description="ISO-8601 last-activity timestamp.")
    message_count: int = Field(0, description="Number of messages in this conversation.")


class ConversationListResponse(BaseModel):
    """Response body for GET /memory/conversations."""

    conversations: list[ConversationSummary]
    total: int


class MessageRecord(BaseModel):
    """A single message within a conversation."""

    id: int
    conversation_id: str
    role: str = Field(..., description="'user', 'assistant', 'system', or 'tool'.")
    content: str
    tool_name: str | None = None
    created_at: str


class ConversationDetailResponse(BaseModel):
    """Response body for GET /memory/conversations/{id}."""

    id: str
    mode: str
    title: str | None = None
    created_at: str
    updated_at: str
    messages: list[MessageRecord]


class ClearConversationResponse(BaseModel):
    """Response body for DELETE /memory/conversations/{id}."""

    id: str
    cleared: bool
    message: str = "Conversation history cleared."


# ─── Episodic Memory Schemas ──────────────────────────────────────────────────

class EpisodicEvent(BaseModel):
    """A single episodic memory event."""

    id: int
    conversation_id: str | None = None
    event_type: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class EpisodicListResponse(BaseModel):
    """Response body for GET /memory/episodic."""

    events: list[EpisodicEvent]
    total: int


# ─── Memory Status Schema ─────────────────────────────────────────────────────

class MemoryStatusResponse(BaseModel):
    """Response body for GET /memory/status."""

    long_term_count: int = Field(..., description="Number of long-term memories stored.")
    conversation_count: int = Field(..., description="Number of stored conversations.")
    episodic_count: int = Field(..., description="Number of recorded episodic events.")
    long_term_enabled: bool
    episodic_enabled: bool
    semantic_enabled: bool
    db_path: str = Field(..., description="Path to the SQLite database file.")
