"""
core/memory/semantic.py

Semantic memory for NyxAI — vector-similarity search over memories.

This module uses ChromaDB as a local vector store and Ollama's
nomic-embed-text model to generate embeddings for memory entries.
It enables similarity-based retrieval: given a user query, return
the most relevant memories to inject into the LLM context.

Architecture:
  User query
    ↓
  Generate query embedding (Ollama nomic-embed-text)
    ↓
  ChromaDB similarity search
    ↓
  Top-K relevant memory IDs
    ↓
  Fetch full memory content from SQLite
    ↓
  Inject into system prompt

This module is OPTIONAL — controlled by SEMANTIC_MEMORY_ENABLED env var.
When disabled, the system falls back to injecting all long-term memories
directly (which works well when the memory count is small).

Prerequisite:
  ollama pull nomic-embed-text
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

# ChromaDB collection name for NyxAI long-term memories
_COLLECTION_NAME = "nyxai_long_term_memories"


class SemanticMemory:
    """
    Vector-similarity search over long-term memories.

    Uses ChromaDB as the local vector store and Ollama's nomic-embed-text
    model for embedding generation. All ChromaDB operations are run in
    a thread pool executor since chromadb is synchronous.

    Args:
        chroma_path: Directory path for ChromaDB persistent storage.
        ollama_base_url: Ollama server URL for embedding requests.
        embedding_model: Ollama model to use for embeddings.
        top_k: Default number of results to return per query.
    """

    def __init__(
        self,
        chroma_path: str,
        ollama_base_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        top_k: int = 5,
    ) -> None:
        self._chroma_path = chroma_path
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._embedding_model = embedding_model
        self._top_k = top_k
        self._collection: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize ChromaDB client and get/create the memory collection.

        This must be called at startup before any embed/search operations.
        Runs ChromaDB initialization in a thread pool (it's synchronous).
        """
        import os

        import chromadb

        os.makedirs(self._chroma_path, exist_ok=True)

        def _init_chroma() -> Any:
            client = chromadb.PersistentClient(path=self._chroma_path)
            return client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

        loop = asyncio.get_event_loop()
        self._collection = await loop.run_in_executor(None, _init_chroma)
        self._initialized = True

        logger.info(
            "semantic_memory_initialized",
            chroma_path=self._chroma_path,
            embedding_model=self._embedding_model,
            collection=_COLLECTION_NAME,
        )

    async def _get_embedding(self, text: str) -> list[float]:
        """
        Call Ollama's embedding API to get a vector for the given text.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            httpx.HTTPStatusError: If the Ollama API returns an error.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._ollama_base_url}/api/embeddings",
                json={"model": self._embedding_model, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["embedding"]

    async def embed_and_store(self, memory_id: int, content: str) -> None:
        """
        Generate an embedding for a memory and store it in ChromaDB.

        The ChromaDB document ID is the string form of the SQLite memory ID,
        so we can look up the full content from SQLite after retrieval.

        Args:
            memory_id: SQLite integer ID of the long-term memory.
            content: Memory content to embed.
        """
        if not self._initialized:
            logger.warning("semantic_memory_not_initialized_skip_embed")
            return

        try:
            embedding = await self._get_embedding(content)
            doc_id = str(memory_id)

            def _upsert() -> None:
                self._collection.upsert(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content],
                )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _upsert)

            logger.debug(
                "semantic_memory_stored",
                memory_id=memory_id,
                content_length=len(content),
            )
        except Exception as exc:
            # Non-fatal — semantic memory is optional
            logger.warning(
                "semantic_memory_embed_failed",
                memory_id=memory_id,
                error=str(exc),
            )

    async def delete_embedding(self, memory_id: int) -> None:
        """
        Remove a memory's embedding from ChromaDB.

        Args:
            memory_id: SQLite integer ID of the memory to remove.
        """
        if not self._initialized:
            return

        try:
            doc_id = str(memory_id)

            def _delete() -> None:
                self._collection.delete(ids=[doc_id])

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _delete)
            logger.debug("semantic_memory_deleted", memory_id=memory_id)
        except Exception as exc:
            logger.warning(
                "semantic_memory_delete_failed",
                memory_id=memory_id,
                error=str(exc),
            )

    async def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Find the most semantically relevant memories for a query.

        Args:
            query: User message or search query.
            top_k: Number of results to return. Defaults to self._top_k.

        Returns:
            List of dicts with 'memory_id' (int) and 'content' (str),
            ordered by relevance (most relevant first).
            Returns empty list if semantic memory is not initialized.
        """
        if not self._initialized:
            return []

        k = top_k if top_k is not None else self._top_k

        try:
            query_embedding = await self._get_embedding(query)

            def _query() -> Any:
                return self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(k, max(1, self._collection.count())),
                    include=["documents", "distances"],
                )

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _query)

            hits = []
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]

            for doc_id, doc in zip(ids, docs):
                hits.append({
                    "memory_id": int(doc_id),
                    "content": doc,
                })

            return hits

        except Exception as exc:
            logger.warning(
                "semantic_memory_search_failed",
                error=str(exc),
            )
            return []
