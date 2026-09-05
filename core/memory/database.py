"""
core/memory/database.py

Async SQLite database layer for NyxAI memory persistence.

This module manages the single shared SQLite connection and defines
the schema for all memory tables. It uses aiosqlite for fully async
non-blocking database access.

Tables:
  - conversations    : Conversation session metadata
  - messages         : All chat messages (linked to a conversation)
  - long_term_memories : User-approved persistent facts
  - episodic_memories  : Notable events and tool executions

Usage:
    db = MemoryDatabase("./data/nyx_memory.db")
    await db.initialize()

    # Use via context manager for auto-close on scope exit
    async with db.connection() as conn:
        await conn.execute("SELECT ...")
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

from core.logging import get_logger

logger = get_logger(__name__)

# Current schema version. Increment this when adding new columns or tables.
SCHEMA_VERSION = 1

# DDL for all tables — created once on first startup if they don't exist.
_CREATE_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    mode        TEXT NOT NULL DEFAULT 'companion',
    title       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tool_name       TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS long_term_memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content     TEXT NOT NULL,
    source      TEXT DEFAULT 'manual',
    tags        TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodic_memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    event_type      TEXT NOT NULL,
    description     TEXT NOT NULL,
    metadata        TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_episodic_conv_id ON episodic_memories(conversation_id);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


class MemoryDatabase:
    """
    Manages the SQLite database connection for NyxAI memory persistence.

    A single instance of this class should be created at startup and
    shared across all memory modules via the MemoryService aggregator.

    Args:
        db_path: Absolute or relative path to the SQLite file.
                 The parent directory will be created if it doesn't exist.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._initialized = False

    async def initialize(self) -> None:
        """
        Create the database file + schema if they don't exist.

        Idempotent — safe to call multiple times.
        Must be called once at application startup.
        """
        db_dir = os.path.dirname(os.path.abspath(self._db_path))
        os.makedirs(db_dir, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as conn:
            await conn.executescript(_CREATE_SCHEMA_SQL)

            cursor = await conn.execute("SELECT COUNT(*) FROM schema_version")
            row = await cursor.fetchone()
            if row and row[0] == 0:
                await conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )

            await conn.commit()

        self._initialized = True
        logger.info(
            "memory_db_initialized",
            db_path=self._db_path,
            schema_version=SCHEMA_VERSION,
        )

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Async context manager that yields a live aiosqlite connection.

        Row factory is set so rows behave like dicts (access by column name).

        Raises:
            RuntimeError: If initialize() was not called first.
        """
        if not self._initialized:
            raise RuntimeError(
                "MemoryDatabase.initialize() must be called before use. "
                "Ensure it is awaited in the application startup lifespan."
            )

        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA journal_mode=WAL")
            yield conn

    @property
    def db_path(self) -> str:
        """Return the configured database file path."""
        return self._db_path
