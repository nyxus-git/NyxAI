"""
tests/test_memory.py

Unit and integration tests for the NyxAI Phase 5 Memory System.

Tests cover:
  - MemoryDatabase schema initialization
  - ShortTermMemory: save, retrieve, trim, clear, list
  - LongTermMemory: add, get_all, delete, tag filtering, format_for_prompt
  - EpisodicMemory: record_event, record_tool_execution, get_recent, filters
  - MemoryService: aggregator coordination, prompt context building
  - Integration: message persists across separate ChatService-like calls
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

from core.brain.llm import MessageRole
from core.memory import MemoryService
from core.memory.database import MemoryDatabase
from core.memory.episodic import EpisodicMemory, EventType
from core.memory.long_term import LongTermMemory
from core.memory.short_term import ShortTermMemory


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def memory_db(tmp_path) -> MemoryDatabase:
    """Create a fresh in-memory-like SQLite database for each test."""
    db_path = str(tmp_path / "test_memory.db")
    db = MemoryDatabase(db_path=db_path)
    await db.initialize()
    return db


@pytest_asyncio.fixture
async def short_term(memory_db: MemoryDatabase) -> ShortTermMemory:
    return ShortTermMemory(db=memory_db, max_history_turns=5)


@pytest_asyncio.fixture
async def long_term(memory_db: MemoryDatabase) -> LongTermMemory:
    return LongTermMemory(db=memory_db)


@pytest_asyncio.fixture
async def episodic(memory_db: MemoryDatabase) -> EpisodicMemory:
    return EpisodicMemory(db=memory_db)


@pytest_asyncio.fixture
async def short_and_episodic(memory_db: MemoryDatabase):
    """Combined fixture for tests that need both ShortTermMemory and EpisodicMemory."""
    st = ShortTermMemory(db=memory_db, max_history_turns=5)
    ep = EpisodicMemory(db=memory_db)
    return st, ep


@pytest_asyncio.fixture
async def memory_service(memory_db: MemoryDatabase) -> MemoryService:
    svc = MemoryService(
        db=memory_db,
        semantic_memory_enabled=False,  # Disable for tests (no Ollama needed)
        long_term_enabled=True,
        episodic_enabled=True,
    )
    await svc.initialize()
    return svc


# ─── MemoryDatabase Tests ─────────────────────────────────────────────────────

class TestMemoryDatabase:
    @pytest.mark.asyncio
    async def test_initialize_creates_schema(self, memory_db: MemoryDatabase) -> None:
        """Verify all expected tables are created on initialization."""
        expected_tables = {
            "schema_version",
            "conversations",
            "messages",
            "long_term_memories",
            "episodic_memories",
        }
        async with memory_db.connection() as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            rows = await cursor.fetchall()
            actual_tables = {row["name"] for row in rows}

        assert expected_tables.issubset(actual_tables), (
            f"Missing tables: {expected_tables - actual_tables}"
        )

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self, tmp_path) -> None:
        """Calling initialize() twice should not raise errors."""
        db_path = str(tmp_path / "idempotent.db")
        db = MemoryDatabase(db_path=db_path)
        await db.initialize()
        await db.initialize()  # Should not raise

    @pytest.mark.asyncio
    async def test_connection_raises_without_init(self, tmp_path) -> None:
        """Using connection() before initialize() should raise RuntimeError."""
        db = MemoryDatabase(db_path=str(tmp_path / "uninit.db"))
        with pytest.raises(RuntimeError, match="initialize\\(\\)"):
            async with db.connection() as conn:
                await conn.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_row_factory_enables_dict_access(self, memory_db: MemoryDatabase) -> None:
        """Rows returned from connection() should support column-name access."""
        async with memory_db.connection() as conn:
            cursor = await conn.execute("SELECT 1 AS value")
            row = await cursor.fetchone()
        assert row["value"] == 1


# ─── ShortTermMemory Tests ────────────────────────────────────────────────────

class TestShortTermMemory:
    @pytest.mark.asyncio
    async def test_save_and_retrieve_messages(self, short_term: ShortTermMemory) -> None:
        """Saved messages should be retrievable in chronological order."""
        conv_id = str(uuid.uuid4())
        await short_term.save_message(conv_id, MessageRole.USER, "Hello")
        await short_term.save_message(conv_id, MessageRole.ASSISTANT, "Hi there!")

        history = await short_term.get_history(conv_id)
        assert len(history) == 2
        assert history[0].role == MessageRole.USER
        assert history[0].content == "Hello"
        assert history[1].role == MessageRole.ASSISTANT
        assert history[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_separate_conversations_are_isolated(self, short_term: ShortTermMemory) -> None:
        """Messages from different conversations must not bleed into each other."""
        conv_a = str(uuid.uuid4())
        conv_b = str(uuid.uuid4())

        await short_term.save_message(conv_a, MessageRole.USER, "Message A")
        await short_term.save_message(conv_b, MessageRole.USER, "Message B")

        history_a = await short_term.get_history(conv_a)
        history_b = await short_term.get_history(conv_b)

        assert len(history_a) == 1
        assert history_a[0].content == "Message A"
        assert len(history_b) == 1
        assert history_b[0].content == "Message B"

    @pytest.mark.asyncio
    async def test_empty_conversation_returns_empty_list(self, short_term: ShortTermMemory) -> None:
        """Getting history for a new/unknown conversation should return []."""
        history = await short_term.get_history(str(uuid.uuid4()))
        assert history == []

    @pytest.mark.asyncio
    async def test_history_trimmed_to_max_turns(self, short_term: ShortTermMemory) -> None:
        """History should be trimmed when it exceeds max_history_turns * 2."""
        conv_id = str(uuid.uuid4())
        # max_history_turns=5 means max 10 messages
        for i in range(7):  # Add 7 user + 7 assistant = 14 messages
            await short_term.save_message(conv_id, MessageRole.USER, f"User {i}")
            await short_term.save_message(conv_id, MessageRole.ASSISTANT, f"Bot {i}")

        history = await short_term.get_history(conv_id)
        assert len(history) <= 10, f"Expected <=10 messages, got {len(history)}"

    @pytest.mark.asyncio
    async def test_clear_conversation(self, short_term: ShortTermMemory) -> None:
        """Clearing a conversation should delete all its messages."""
        conv_id = str(uuid.uuid4())
        await short_term.save_message(conv_id, MessageRole.USER, "Test")
        await short_term.clear_conversation(conv_id)

        history = await short_term.get_history(conv_id)
        assert history == []

    @pytest.mark.asyncio
    async def test_clear_nonexistent_conversation_returns_false(
        self, short_term: ShortTermMemory
    ) -> None:
        """Clearing an unknown conversation should return False gracefully."""
        result = await short_term.clear_conversation(str(uuid.uuid4()))
        assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations(self, short_term: ShortTermMemory) -> None:
        """list_conversations should return all sessions with message counts."""
        conv_a = str(uuid.uuid4())
        conv_b = str(uuid.uuid4())
        await short_term.save_message(conv_a, MessageRole.USER, "Hello")
        await short_term.save_message(conv_b, MessageRole.USER, "Hi")

        convs = await short_term.list_conversations(limit=10)
        assert len(convs) == 2
        # Each should have a message_count >= 1
        for c in convs:
            assert c["message_count"] >= 1

    @pytest.mark.asyncio
    async def test_ensure_conversation_idempotent(self, short_term: ShortTermMemory) -> None:
        """ensure_conversation called multiple times should not error."""
        conv_id = str(uuid.uuid4())
        await short_term.ensure_conversation(conv_id, mode="agent")
        await short_term.ensure_conversation(conv_id, mode="agent")  # Should not raise


# ─── LongTermMemory Tests ─────────────────────────────────────────────────────

class TestLongTermMemory:
    @pytest.mark.asyncio
    async def test_add_and_retrieve_memory(self, long_term: LongTermMemory) -> None:
        """Added memories should appear in get_all()."""
        mem_id = await long_term.add_memory(
            content="User prefers Hinglish responses.",
            source="manual",
            tags=["preference"],
        )
        memories = await long_term.get_all()
        assert len(memories) == 1
        assert memories[0]["id"] == mem_id
        assert memories[0]["content"] == "User prefers Hinglish responses."
        assert memories[0]["source"] == "manual"

    @pytest.mark.asyncio
    async def test_add_memory_returns_id(self, long_term: LongTermMemory) -> None:
        """add_memory should return a positive integer ID."""
        mem_id = await long_term.add_memory("Test memory")
        assert isinstance(mem_id, int)
        assert mem_id > 0

    @pytest.mark.asyncio
    async def test_delete_memory(self, long_term: LongTermMemory) -> None:
        """Deleting a memory by ID should remove it from get_all()."""
        mem_id = await long_term.add_memory("To be deleted")
        deleted = await long_term.delete_memory(mem_id)
        assert deleted is True

        memories = await long_term.get_all()
        ids = [m["id"] for m in memories]
        assert mem_id not in ids

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, long_term: LongTermMemory) -> None:
        """Deleting a memory that doesn't exist should return False."""
        result = await long_term.delete_memory(99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_filter_by_tag(self, long_term: LongTermMemory) -> None:
        """get_all(tag=...) should only return memories with that tag."""
        await long_term.add_memory("Memory A", tags=["preference"])
        await long_term.add_memory("Memory B", tags=["project"])

        pref_memories = await long_term.get_all(tag="preference")
        assert len(pref_memories) == 1
        assert pref_memories[0]["content"] == "Memory A"

    @pytest.mark.asyncio
    async def test_format_for_prompt_empty(self, long_term: LongTermMemory) -> None:
        """format_for_prompt with no memories should return empty string."""
        result = await long_term.format_for_prompt()
        assert result == ""

    @pytest.mark.asyncio
    async def test_format_for_prompt_with_memories(self, long_term: LongTermMemory) -> None:
        """format_for_prompt should include all memories as bullet points."""
        await long_term.add_memory("User prefers concise answers.")
        await long_term.add_memory("User uses Arch Linux with Hyprland.")

        result = await long_term.format_for_prompt()
        assert "## What I Know About You" in result
        assert "User prefers concise answers." in result
        assert "User uses Arch Linux with Hyprland." in result

    @pytest.mark.asyncio
    async def test_update_memory(self, long_term: LongTermMemory) -> None:
        """Updating a memory should change its content."""
        mem_id = await long_term.add_memory("Original content")
        updated = await long_term.update_memory(mem_id, "Updated content")
        assert updated is True

        memories = await long_term.get_all()
        mem = next(m for m in memories if m["id"] == mem_id)
        assert mem["content"] == "Updated content"


# ─── EpisodicMemory Tests ─────────────────────────────────────────────────────

class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_record_and_retrieve_event(self, short_and_episodic) -> None:
        """Recorded events should be retrievable via get_recent()."""
        st, episodic = short_and_episodic
        conv_id = str(uuid.uuid4())
        # Create the conversation row first (FK requirement)
        await st.ensure_conversation(conv_id)
        event_id = await episodic.record_event(
            event_type=EventType.TOOL_EXECUTION,
            description="Opened VS Code",
            conversation_id=conv_id,
            metadata={"tool": "open_application", "app": "code"},
        )
        assert isinstance(event_id, int)
        assert event_id > 0

        events = await episodic.get_recent(limit=5)
        assert len(events) == 1
        assert events[0]["description"] == "Opened VS Code"
        assert events[0]["event_type"] == EventType.TOOL_EXECUTION
        assert events[0]["metadata"]["tool"] == "open_application"

    @pytest.mark.asyncio
    async def test_record_tool_execution_convenience(self, episodic: EpisodicMemory) -> None:
        """record_tool_execution should create an event with correct metadata."""
        event_id = await episodic.record_tool_execution(
            tool_name="search_web",
            description="Searched web for FastAPI tutorials",
            tool_args={"query": "FastAPI tutorial"},
        )
        events = await episodic.get_recent(limit=1)
        assert events[0]["metadata"]["tool"] == "search_web"
        assert events[0]["metadata"]["args"]["query"] == "FastAPI tutorial"

    @pytest.mark.asyncio
    async def test_filter_by_event_type(self, episodic: EpisodicMemory) -> None:
        """get_recent(event_type=...) should only return matching events."""
        await episodic.record_event(EventType.TOOL_EXECUTION, "Tool event")
        await episodic.record_event(EventType.SESSION_START, "Session started")

        tool_events = await episodic.get_recent(event_type=EventType.TOOL_EXECUTION)
        assert len(tool_events) == 1
        assert tool_events[0]["event_type"] == EventType.TOOL_EXECUTION

    @pytest.mark.asyncio
    async def test_filter_by_conversation_id(self, short_and_episodic) -> None:
        """get_recent(conversation_id=...) should only return events for that conversation."""
        st, episodic = short_and_episodic
        conv_a = str(uuid.uuid4())
        conv_b = str(uuid.uuid4())
        # Create conversation rows first (FK requirement)
        await st.ensure_conversation(conv_a)
        await st.ensure_conversation(conv_b)

        await episodic.record_event(EventType.TOOL_EXECUTION, "Event A", conversation_id=conv_a)
        await episodic.record_event(EventType.TOOL_EXECUTION, "Event B", conversation_id=conv_b)

        events_a = await episodic.get_recent(conversation_id=conv_a)
        assert len(events_a) == 1
        assert events_a[0]["description"] == "Event A"

    @pytest.mark.asyncio
    async def test_metadata_serialization(self, episodic: EpisodicMemory) -> None:
        """Metadata stored as JSON should be deserialized back to a dict."""
        meta = {"key": "value", "number": 42, "nested": {"a": 1}}
        await episodic.record_event(EventType.USER_ACTION, "Action", metadata=meta)

        events = await episodic.get_recent(limit=1)
        assert events[0]["metadata"] == meta

    @pytest.mark.asyncio
    async def test_get_session_summary(self, short_and_episodic) -> None:
        """get_session_summary should return a bullet-point string of events."""
        st, episodic = short_and_episodic
        conv_id = str(uuid.uuid4())
        # Create conversation row first (FK requirement)
        await st.ensure_conversation(conv_id)
        await episodic.record_event(EventType.TOOL_EXECUTION, "Opened Firefox", conversation_id=conv_id)
        await episodic.record_event(EventType.TOOL_EXECUTION, "Searched YouTube", conversation_id=conv_id)

        summary = await episodic.get_session_summary(conv_id)
        assert "Opened Firefox" in summary
        assert "Searched YouTube" in summary


# ─── MemoryService Aggregator Tests ───────────────────────────────────────────

class TestMemoryService:
    @pytest.mark.asyncio
    async def test_add_and_delete_long_term_via_service(
        self, memory_service: MemoryService
    ) -> None:
        """MemoryService.add_long_term_memory / delete_long_term_memory should work."""
        mem_id = await memory_service.add_long_term_memory(
            content="User uses EndeavourOS.",
            source="manual",
        )
        assert mem_id > 0

        deleted = await memory_service.delete_long_term_memory(mem_id)
        assert deleted is True

        memories = await memory_service.long_term.get_all()
        assert all(m["id"] != mem_id for m in memories)

    @pytest.mark.asyncio
    async def test_build_system_prompt_context_empty(
        self, memory_service: MemoryService
    ) -> None:
        """With no memories, build_system_prompt_context should return empty string."""
        ctx = await memory_service.build_system_prompt_context(query="Test")
        assert ctx == ""

    @pytest.mark.asyncio
    async def test_build_system_prompt_context_with_memories(
        self, memory_service: MemoryService
    ) -> None:
        """With long-term memories, context block should include them."""
        await memory_service.add_long_term_memory("User prefers Hinglish.")
        ctx = await memory_service.build_system_prompt_context(query="Anything")
        assert "User prefers Hinglish." in ctx
        assert "## What I Know About You" in ctx

    @pytest.mark.asyncio
    async def test_short_term_accessible_via_service(
        self, memory_service: MemoryService
    ) -> None:
        """memory_service.short_term should be a working ShortTermMemory instance."""
        conv_id = str(uuid.uuid4())
        await memory_service.short_term.save_message(conv_id, MessageRole.USER, "Hello")
        history = await memory_service.short_term.get_history(conv_id)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_episodic_accessible_via_service(
        self, memory_service: MemoryService
    ) -> None:
        """memory_service.episodic should be a working EpisodicMemory instance."""
        await memory_service.episodic.record_event(
            event_type=EventType.SESSION_START,
            description="Test session started",
        )
        events = await memory_service.episodic.get_recent(limit=5)
        assert len(events) == 1


# ─── Integration Test ─────────────────────────────────────────────────────────

class TestMemoryIntegration:
    @pytest.mark.asyncio
    async def test_conversation_persists_across_service_instances(
        self, tmp_path
    ) -> None:
        """
        Simulate a restart: create a service, save messages, recreate service,
        verify history is still retrievable.
        """
        db_path = str(tmp_path / "persist_test.db")

        # First "session"
        db1 = MemoryDatabase(db_path=db_path)
        await db1.initialize()
        st1 = ShortTermMemory(db=db1)
        conv_id = str(uuid.uuid4())
        await st1.save_message(conv_id, MessageRole.USER, "Remember this!")
        await st1.save_message(conv_id, MessageRole.ASSISTANT, "Got it.")

        # Second "session" (simulates restart — new object, same file)
        db2 = MemoryDatabase(db_path=db_path)
        await db2.initialize()
        st2 = ShortTermMemory(db=db2)
        history = await st2.get_history(conv_id)

        assert len(history) == 2
        assert history[0].content == "Remember this!"
        assert history[1].content == "Got it."

    @pytest.mark.asyncio
    async def test_full_memory_lifecycle(self, memory_service: MemoryService) -> None:
        """
        End-to-end test of the complete memory lifecycle:
        add memory → build context → verify in prompt → delete → verify gone.
        """
        # Add a long-term memory
        mem_id = await memory_service.add_long_term_memory(
            content="User is building NyxAI on EndeavourOS.",
            source="manual",
        )

        # Context should include it
        ctx = await memory_service.build_system_prompt_context(query="What project?")
        assert "NyxAI on EndeavourOS" in ctx

        # Delete it
        await memory_service.delete_long_term_memory(mem_id)

        # Context should no longer include it
        ctx_after = await memory_service.build_system_prompt_context(query="What project?")
        assert "NyxAI on EndeavourOS" not in ctx_after
