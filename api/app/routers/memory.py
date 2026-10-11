"""
api/app/routers/memory.py

NyxAI Memory API router.

Provides REST endpoints for user-facing memory management:
  - View, add, and delete long-term memories
  - List and clear conversation history
  - View episodic events (auto-generated activity log)
  - Memory status overview

All state is accessed via app.state.memory_service (MemoryService)
which is initialized in the application lifespan.

Endpoints:
  GET    /memory/status                 — Overview of memory system
  GET    /memory/long-term              — List all long-term memories
  POST   /memory/long-term              — Add a new long-term memory
  DELETE /memory/long-term/{id}         — Delete a long-term memory
  GET    /memory/conversations          — List recent conversations
  GET    /memory/conversations/{id}     — Get messages in a conversation
  DELETE /memory/conversations/{id}     — Clear a conversation's messages
  GET    /memory/episodic               — List recent episodic events
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from api.app.schemas.memory import (
    AddMemoryRequest,
    AddMemoryResponse,
    ClearConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    DeleteMemoryResponse,
    EpisodicListResponse,
    MemoryListResponse,
    MemoryStatusResponse,
)
from core.logging import get_logger
from core.memory import MemoryService

logger = get_logger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


def _get_memory_service(request: Request) -> MemoryService:
    """Extract MemoryService from app.state."""
    service: MemoryService | None = getattr(request.app.state, "memory_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Memory service is not initialized. Check startup logs.",
        )
    return service


# Status

@router.get("/status", response_model=MemoryStatusResponse, summary="Memory system status")
async def get_memory_status(request: Request) -> MemoryStatusResponse:
    """
    Return an overview of the memory system state.

    Shows counts for each memory layer and feature flag status.
    Useful for the companion UI status indicator.
    """
    svc = _get_memory_service(request)
    settings = request.app.state.settings

    lt_memories = await svc.long_term.get_all()
    conversations = await svc.short_term.list_conversations(limit=9999)
    episodic_events = await svc.episodic.get_recent(limit=9999)

    return MemoryStatusResponse(
        long_term_count=len(lt_memories),
        conversation_count=len(conversations),
        episodic_count=len(episodic_events),
        long_term_enabled=settings.long_term_memory_enabled,
        episodic_enabled=settings.episodic_memory_enabled,
        semantic_enabled=settings.semantic_memory_enabled,
        db_path=settings.memory_db_path,
    )


# Long-Term Memories

@router.get(
    "/long-term",
    response_model=MemoryListResponse,
    summary="List all long-term memories",
)
async def list_long_term_memories(
    request: Request,
    tag: str | None = Query(default=None, description="Filter memories by tag"),
) -> MemoryListResponse:
    """
    Return all stored long-term memories.

    Optionally filter by a tag string. Memories are returned newest first.
    """
    svc = _get_memory_service(request)
    memories = await svc.long_term.get_all(tag=tag)

    logger.info("memory_list_long_term", count=len(memories), tag=tag)
    return MemoryListResponse(memories=memories, total=len(memories))  # type: ignore[arg-type]


@router.post(
    "/long-term",
    response_model=AddMemoryResponse,
    status_code=201,
    summary="Add a new long-term memory",
)
async def add_long_term_memory(
    request: Request,
    body: AddMemoryRequest,
) -> AddMemoryResponse:
    """
    Store a new long-term memory.

    The memory will be injected into the LLM system prompt on all future
    conversations. If semantic memory is enabled, it is also embedded
    into ChromaDB for similarity search.
    """
    svc = _get_memory_service(request)
    memory_id = await svc.add_long_term_memory(
        content=body.content,
        source=body.source,
        tags=body.tags,
    )

    logger.info(
        "memory_add_long_term",
        memory_id=memory_id,
        source=body.source,
    )
    return AddMemoryResponse(
        id=memory_id,
        content=body.content,
        message="Memory saved successfully.",
    )


@router.delete(
    "/long-term/{memory_id}",
    response_model=DeleteMemoryResponse,
    summary="Delete a long-term memory",
)
async def delete_long_term_memory(
    request: Request,
    memory_id: int,
) -> DeleteMemoryResponse:
    """
    Delete a long-term memory by ID.

    Also removes the embedding from ChromaDB if semantic memory is enabled.
    Returns 404 if the memory ID does not exist.
    """
    svc = _get_memory_service(request)
    deleted = await svc.delete_long_term_memory(memory_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Memory with id={memory_id} not found.",
        )

    logger.info("memory_delete_long_term", memory_id=memory_id)
    return DeleteMemoryResponse(
        id=memory_id,
        deleted=True,
        message=f"Memory {memory_id} deleted successfully.",
    )


# Conversations

@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List recent conversations",
)
async def list_conversations(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Max conversations to return"),
) -> ConversationListResponse:
    """
    Return recent conversation sessions ordered by last activity.

    Each item includes a message count and the conversation mode.
    """
    svc = _get_memory_service(request)
    conversations = await svc.short_term.list_conversations(limit=limit)

    return ConversationListResponse(
        conversations=conversations,  # type: ignore[arg-type]
        total=len(conversations),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get messages in a conversation",
)
async def get_conversation(
    request: Request,
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> ConversationDetailResponse:
    """
    Return the full message history for a specific conversation.

    Returns 404 if the conversation ID is not found.
    """
    svc = _get_memory_service(request)

    # Verify conversation exists
    conversations = await svc.short_term.list_conversations(limit=9999)
    conv = next((c for c in conversations if c["id"] == conversation_id), None)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    history = await svc.short_term.get_history(conversation_id, limit=limit)

    messages = []
    for i, msg in enumerate(history):
        messages.append({
            "id": i + 1,
            "conversation_id": conversation_id,
            "role": msg.role.value,
            "content": msg.content,
            "tool_name": None,
            "created_at": conv["created_at"],
        })

    return ConversationDetailResponse(
        id=conv["id"],
        mode=conv["mode"],
        title=conv.get("title"),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        messages=messages,  # type: ignore[arg-type]
    )


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ClearConversationResponse,
    summary="Clear a conversation's message history",
)
async def clear_conversation(
    request: Request,
    conversation_id: str,
) -> ClearConversationResponse:
    """
    Delete all messages in a conversation.

    The conversation metadata row is kept; only messages are deleted.
    Returns 404 if the conversation is not found.
    """
    svc = _get_memory_service(request)
    cleared = await svc.short_term.clear_conversation(conversation_id)

    if not cleared:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    logger.info("memory_clear_conversation", conversation_id=conversation_id)
    return ClearConversationResponse(
        id=conversation_id,
        cleared=True,
        message="Conversation history cleared successfully.",
    )


# Episodic Memory

@router.get(
    "/episodic",
    response_model=EpisodicListResponse,
    summary="List recent episodic events",
)
async def list_episodic_events(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    conversation_id: str | None = Query(default=None, description="Filter by conversation"),
) -> EpisodicListResponse:
    """
    Return recent auto-generated episodic events.

    Events include tool executions, session starts, and other notable actions.
    Ordered newest first.
    """
    svc = _get_memory_service(request)
    events = await svc.episodic.get_recent(
        limit=limit,
        event_type=event_type,
        conversation_id=conversation_id,
    )

    return EpisodicListResponse(events=events, total=len(events))  # type: ignore[arg-type]
