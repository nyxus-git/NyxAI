"""
core/memory/__init__.py

Memory system for NyxAI — Phase 5.

Exports the MemoryService aggregator which is the single dependency
injected into ChatService and API routers. This keeps the interface
simple: callers only need one object to access all memory layers.

Memory layers:
  - ShortTermMemory  : SQLite-backed conversation history (per session)
  - LongTermMemory   : Persistent user facts injected into every prompt
  - EpisodicMemory   : Auto-generated event journal (tool executions etc.)
  - SemanticMemory   : ChromaDB vector search (optional)
"""

from __future__ import annotations

from core.memory.database import MemoryDatabase
from core.memory.episodic import EpisodicMemory
from core.memory.long_term import LongTermMemory
from core.memory.semantic import SemanticMemory
from core.memory.short_term import ShortTermMemory

__all__ = [
    "MemoryDatabase",
    "ShortTermMemory",
    "LongTermMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "MemoryService",
]


class MemoryService:
    """
    Aggregator for all NyxAI memory layers.

    This is the single object injected into ChatService and API routers.
    It provides unified access to all memory operations and handles
    cross-layer coordination (e.g. embedding a new long-term memory
    also stores it in ChromaDB if semantic memory is enabled).

    Args:
        db: Initialized MemoryDatabase instance.
        semantic_memory_enabled: Whether to use ChromaDB for retrieval.
        ollama_base_url: Ollama URL for embedding generation.
        embedding_model: Ollama model for embeddings.
        chroma_path: ChromaDB storage directory path.
        top_k: Number of semantic search results to surface.
        max_history_turns: Max turns to retain in short-term memory.
        long_term_enabled: Whether to inject long-term memories into prompts.
        episodic_enabled: Whether to record episodic events.
    """

    def __init__(
        self,
        db: MemoryDatabase,
        semantic_memory_enabled: bool = False,
        ollama_base_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        chroma_path: str = "./data/chroma",
        top_k: int = 5,
        max_history_turns: int = 20,
        long_term_enabled: bool = True,
        episodic_enabled: bool = True,
    ) -> None:
        self._db = db
        self._long_term_enabled = long_term_enabled
        self._episodic_enabled = episodic_enabled
        self._semantic_enabled = semantic_memory_enabled

        self.short_term = ShortTermMemory(db=db, max_history_turns=max_history_turns)
        self.long_term = LongTermMemory(db=db)
        self.episodic = EpisodicMemory(db=db)
        self.semantic = SemanticMemory(
            chroma_path=chroma_path,
            ollama_base_url=ollama_base_url,
            embedding_model=embedding_model,
            top_k=top_k,
        )

    async def initialize(self) -> None:
        """
        Initialize all memory layers.

        Must be called once at application startup (after MemoryDatabase.initialize()).
        """
        if self._semantic_enabled:
            await self.semantic.initialize()

        from core.logging import get_logger
        logger = get_logger(__name__)
        logger.info(
            "memory_service_initialized",
            long_term_enabled=self._long_term_enabled,
            episodic_enabled=self._episodic_enabled,
            semantic_enabled=self._semantic_enabled,
        )

    async def build_system_prompt_context(self, query: str = "") -> str:
        """
        Build a memory context block to append to the system prompt.

        Combines:
          1. Long-term memories (always, if enabled)
          2. Semantically relevant memories (if semantic memory is enabled)

        Args:
            query: Current user message (used for semantic search if enabled).

        Returns:
            A formatted string to append to the system prompt.
            Empty string if no relevant memories exist.
        """
        sections = []

        # Long-term memories — always inject when enabled
        if self._long_term_enabled:
            lt_block = await self.long_term.format_for_prompt()
            if lt_block:
                sections.append(lt_block)

        # Semantic retrieval — inject most relevant memories
        if self._semantic_enabled and query:
            hits = await self.semantic.search(query)
            if hits:
                lines = ["## Relevant Context From Memory"]
                for hit in hits:
                    lines.append(f"- {hit['content']}")
                sections.append("\n".join(lines))

        return "\n\n".join(sections)

    async def add_long_term_memory(
        self,
        content: str,
        source: str = "manual",
        tags: list[str] | None = None,
    ) -> int:
        """
        Add a long-term memory and index it in ChromaDB if semantic is enabled.

        Args:
            content: Memory content text.
            source: Origin of the memory.
            tags: Optional tag list.

        Returns:
            SQLite integer ID of the new memory.
        """
        memory_id = await self.long_term.add_memory(
            content=content,
            source=source,
            tags=tags,
        )
        if self._semantic_enabled:
            await self.semantic.embed_and_store(memory_id, content)
        return memory_id

    async def delete_long_term_memory(self, memory_id: int) -> bool:
        """
        Delete a long-term memory from SQLite and ChromaDB.

        Args:
            memory_id: Integer ID of the memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        deleted = await self.long_term.delete_memory(memory_id)
        if deleted and self._semantic_enabled:
            await self.semantic.delete_embedding(memory_id)
        return deleted
