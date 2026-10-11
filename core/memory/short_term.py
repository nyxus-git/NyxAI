"""
core/memory/short_term.py

SQLite-backed short-term conversation memory for NyxAI.

Replaces the in-memory defaultdict in ChatService with persistent
storage. Conversations now survive backend restarts.

Responsibilities:
  - Persist every message turn to the `conversations` + `messages` tables
  - Retrieve recent conversation history as Message objects
  - Trim old messages when MAX_HISTORY_TURNS is exceeded
  - List recent conversations for the memory API
  - Clear individual conversations

Provides persistent storage across sessions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.brain.llm import Message, MessageRole
from core.logging import get_logger
from core.memory.database import MemoryDatabase

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ShortTermMemory:
    """
    Manages per-conversation message history backed by SQLite.

    Conversations are keyed by UUID string. Each turn (user + assistant)
    is persisted atomically. History is trimmed to MAX_HISTORY_TURNS
    to keep the context window manageable.

    Args:
        db: Initialized MemoryDatabase instance.
        max_history_turns: Maximum user+assistant pairs to retain per session.
    """

    def __init__(self, db: MemoryDatabase, max_history_turns: int = 20) -> None:
        self._db = db
        self._max_messages = max_history_turns * 2  # user + assistant pairs

    async def ensure_conversation(
        self,
        conversation_id: str,
        mode: str = "companion",
        title: str | None = None,
    ) -> None:
        """
        Create a conversation row if it doesn't already exist.

        Safe to call on every request — uses INSERT OR IGNORE semantics
        so existing conversations are never overwritten.

        Args:
            conversation_id: UUID string for this session.
            mode: 'companion' or 'agent'.
            title: Optional display title.
        """
        now = _utcnow()
        async with self._db.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO conversations (id, mode, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, mode, title, now, now),
            )
            await conn.commit()

    async def save_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        tool_name: str | None = None,
    ) -> None:
        """
        Persist a single message to the database.

        Also updates the `updated_at` timestamp on the parent conversation
        and trims history if it exceeds MAX_HISTORY_TURNS.

        Args:
            conversation_id: UUID string of the session.
            role: MessageRole enum value.
            content: Message text content.
            tool_name: Optional tool name (for tool result messages).
        """
        now = _utcnow()
        async with self._db.connection() as conn:
            # Upsert: create conversation row if needed (handles race-free init)
            await conn.execute(
                """
                INSERT OR IGNORE INTO conversations (id, mode, created_at, updated_at)
                VALUES (?, 'companion', ?, ?)
                """,
                (conversation_id, now, now),
            )

            # Insert the message
            await conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, tool_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role.value, content, tool_name, now),
            )

            # Update conversation timestamp
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

            await conn.commit()

        # Trim old messages asynchronously (fire and don't block)
        await self._trim_history(conversation_id)

        logger.debug(
            "short_term_message_saved",
            conversation_id=conversation_id,
            role=role.value,
            content_length=len(content),
        )

    async def get_history(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        """
        Return conversation history as a list of Message objects.

        Messages are returned in chronological order (oldest first),
        ready to prepend to the LLM context window.

        Args:
            conversation_id: UUID string of the session.
            limit: Optional max number of messages to return.
                   Defaults to MAX_HISTORY_TURNS * 2.

        Returns:
            List of Message objects in chronological order.
        """
        max_rows = limit if limit is not None else self._max_messages
        async with self._db.connection() as conn:
            # Fetch the most recent N messages in reverse, then flip
            cursor = await conn.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, created_at
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) sub
                ORDER BY created_at ASC
                """,
                (conversation_id, max_rows),
            )
            rows = await cursor.fetchall()

        history = []
        for row in rows:
            try:
                role = MessageRole(row["role"])
                history.append(Message(role=role, content=row["content"]))
            except ValueError:
                # Unknown role — skip (defensive)
                logger.warning(
                    "short_term_unknown_role",
                    role=row["role"],
                    conversation_id=conversation_id,
                )

        return history

    async def clear_conversation(self, conversation_id: str) -> bool:
        """
        Delete all messages for a conversation (keep the conversation row).

        Args:
            conversation_id: UUID string to clear.

        Returns:
            True if the conversation existed and was cleared, False otherwise.
        """
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            exists = await cursor.fetchone()
            if not exists:
                return False

            await conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_utcnow(), conversation_id),
            )
            await conn.commit()

        logger.info("short_term_conversation_cleared", conversation_id=conversation_id)
        return True

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        """
        Return recent conversations ordered by last activity.

        Args:
            limit: Maximum number of conversations to return.

        Returns:
            List of dicts with id, mode, title, created_at, updated_at,
            and message_count fields.
        """
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    c.id, c.mode, c.title, c.created_at, c.updated_at,
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def _trim_history(self, conversation_id: str) -> None:
        """
        Delete oldest messages if the conversation exceeds MAX_HISTORY_TURNS.

        Keeps the most recent `max_messages` rows, deleting the surplus.

        Args:
            conversation_id: UUID string of the session to trim.
        """
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            row = await cursor.fetchone()
            total = row[0] if row else 0

            if total > self._max_messages:
                surplus = total - self._max_messages
                await conn.execute(
                    """
                    DELETE FROM messages WHERE id IN (
                        SELECT id FROM messages
                        WHERE conversation_id = ?
                        ORDER BY id ASC
                        LIMIT ?
                    )
                    """,
                    (conversation_id, surplus),
                )
                await conn.commit()
                logger.debug(
                    "short_term_history_trimmed",
                    conversation_id=conversation_id,
                    removed=surplus,
                )
