"""
api/app/services/chat_service.py

Chat orchestration service for NyxAI — Phase 5 (Memory-Aware).

This service sits between the API router and the LLM/Agent layer.
It is responsible for:
  - Managing PERSISTENT conversation history via MemoryService (Phase 5)
  - Routing requests to the correct handler based on mode:
      * mode="companion" → direct LLM call
      * mode="agent"     → NyxAgent tool-calling loop
  - Injecting long-term memories + semantic context into the system prompt
  - Auto-recording tool executions as episodic events
  - Building the message list (system prompt + memory context + history + new message)

Phase 5 changes from Phase 1/2:
  - Replaced in-memory defaultdict with ShortTermMemory (SQLite-backed)
  - Added MemoryService injection for long-term + episodic + semantic memory
  - Memory context is appended to the system prompt on each request
  - Tool executions are recorded as episodic events automatically
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from core.agent.schemas import AgentMode
from core.brain.llm import LLMProvider, Message, MessageRole
from core.brain.prompts import get_system_prompt
from core.logging import get_logger
from core.memory import MemoryService

if TYPE_CHECKING:
    from core.agent.agent import NyxAgent

logger = get_logger(__name__)


class ChatService:
    """
    Manages conversational interactions with the LLM (companion mode)
    and the NyxAgent (agent mode).

    Conversation history is persisted to SQLite via MemoryService.
    Long-term memories and episodic context are injected into each request.

    Args:
        llm_provider: Any LLMProvider implementation. Injected at startup.
        memory_service: MemoryService for persistent history + memory injection.
        agent: Optional NyxAgent for tool-calling mode. If None, agent mode
               falls back to companion mode with a warning.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        memory_service: MemoryService,
        agent: "NyxAgent | None" = None,
    ) -> None:
        self._llm = llm_provider
        self._memory = memory_service
        self._agent = agent

        logger.info(
            "chat_service_initialized",
            provider=type(llm_provider).__name__,
            model=llm_provider.get_model_name(),
            agent_enabled=agent is not None,
            memory_enabled=True,
        )

    async def chat(
        self,
        message: str,
        conversation_id: uuid.UUID | None = None,
        mode: AgentMode = AgentMode.COMPANION,
    ) -> tuple[str, uuid.UUID, str | None, dict | None]:
        """
        Process a user message and return NyxAI's response.

        Routes to the appropriate handler based on mode:
          - COMPANION → direct LLM conversation
          - AGENT     → NyxAgent tool-calling loop

        Args:
            message: The user's input text.
            conversation_id: Optional UUID to continue an existing conversation.
                             If None, a new conversation is started.
            mode: Operating mode — COMPANION or AGENT.

        Returns:
            A tuple of (response_text, conversation_id, tool_used, tool_result).
        """
        # Generate a new ID if this is a fresh conversation
        if conversation_id is None:
            conversation_id = uuid.uuid4()
            logger.info(
                "chat_new_conversation",
                conversation_id=str(conversation_id),
                mode=mode.value,
            )
        else:
            logger.info(
                "chat_continue_conversation",
                conversation_id=str(conversation_id),
                mode=mode.value,
            )

        conv_key = str(conversation_id)

        # Ensure conversation row exists in SQLite
        await self._memory.short_term.ensure_conversation(
            conversation_id=conv_key,
            mode=mode.value,
        )

        # ── Route to the correct handler ─────────────────────────────────────
        if mode == AgentMode.AGENT and self._agent is not None:
            response_text, tool_used, tool_result = await self._handle_agent(
                message=message,
                conv_key=conv_key,
            )
        else:
            if mode == AgentMode.AGENT and self._agent is None:
                logger.warning(
                    "chat_agent_not_available",
                    message="Agent mode requested but NyxAgent not initialized. "
                            "Falling back to companion mode.",
                )
            response_text, tool_used, tool_result = await self._handle_companion(
                message=message,
                conv_key=conv_key,
            )

        return response_text, conversation_id, tool_used, tool_result

    async def _build_system_message(self, query: str) -> Message:
        """
        Build the system message with long-term memory context injected.

        The base system prompt is extended with:
          - Long-term memories (user facts + preferences)
          - Semantically relevant memories (if semantic memory is enabled)

        Args:
            query: Current user message (used for semantic search context).

        Returns:
            A Message object with role=SYSTEM.
        """
        base_prompt = get_system_prompt(compact=False)
        memory_context = await self._memory.build_system_prompt_context(query=query)

        if memory_context:
            full_prompt = f"{base_prompt}\n\n{memory_context}"
        else:
            full_prompt = base_prompt

        return Message(role=MessageRole.SYSTEM, content=full_prompt)

    async def _handle_companion(
        self,
        message: str,
        conv_key: str,
    ) -> tuple[str, None, None]:
        """
        Handle a companion mode request — pure LLM conversation, no tools.

        Retrieves persistent history from SQLite, injects memory context
        into the system prompt, calls LLM, then persists the new turn.

        Returns:
            (response_text, None, None) — no tool used in companion mode.
        """
        # Retrieve persistent history from SQLite
        history = await self._memory.short_term.get_history(conv_key)

        # Build memory-aware system message
        system_message = await self._build_system_message(query=message)
        user_message = Message(role=MessageRole.USER, content=message)
        messages_to_send = [system_message] + history + [user_message]

        logger.debug(
            "companion_sending_to_llm",
            conversation_id=conv_key,
            total_messages=len(messages_to_send),
            history_length=len(history),
        )

        llm_response = await self._llm.chat(messages_to_send)

        # Persist both messages to SQLite
        await self._memory.short_term.save_message(
            conversation_id=conv_key,
            role=MessageRole.USER,
            content=message,
        )
        await self._memory.short_term.save_message(
            conversation_id=conv_key,
            role=MessageRole.ASSISTANT,
            content=llm_response.content,
        )

        logger.info(
            "companion_complete",
            conversation_id=conv_key,
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        return llm_response.content, None, None

    async def _handle_agent(
        self,
        message: str,
        conv_key: str,
    ) -> tuple[str, str | None, dict | None]:
        """
        Handle an agent mode request — tool-calling agentic loop.

        Retrieves persistent history, delegates to NyxAgent, persists the
        result turn, and records tool executions as episodic events.

        Returns:
            (response_text, tool_used, tool_result)
        """
        # Retrieve persistent history from SQLite
        history = await self._memory.short_term.get_history(conv_key)

        logger.debug(
            "agent_delegating",
            conversation_id=conv_key,
            history_length=len(history),
        )

        assert self._agent is not None, "_handle_agent called without an initialized NyxAgent"
        agent_response = await self._agent.run(
            message=message,
            history=history,
        )

        # Persist both messages
        await self._memory.short_term.save_message(
            conversation_id=conv_key,
            role=MessageRole.USER,
            content=message,
        )
        await self._memory.short_term.save_message(
            conversation_id=conv_key,
            role=MessageRole.ASSISTANT,
            content=agent_response.content,
        )

        # Record tool execution as episodic event if a tool was used
        if agent_response.tool_used and self._memory._episodic_enabled:
            await self._memory.episodic.record_tool_execution(
                tool_name=agent_response.tool_used,
                description=f"Executed tool: {agent_response.tool_used}",
                conversation_id=conv_key,
                tool_result=agent_response.tool_result,
            )

        logger.info(
            "agent_complete",
            conversation_id=conv_key,
            model=agent_response.model,
            tool_used=agent_response.tool_used,
            iterations=agent_response.iterations,
        )

        return agent_response.content, agent_response.tool_used, agent_response.tool_result

    def get_history(self, conversation_id: uuid.UUID) -> list[Message]:
        """
        Compatibility shim — returns empty list.

        Use memory_service.short_term.get_history() for async history access.
        Kept for API backwards compatibility during the Phase 5 transition.

        Args:
            conversation_id: Ignored.

        Returns:
            Empty list.
        """
        logger.warning(
            "chat_service_get_history_deprecated",
            message="Use MemoryService.short_term.get_history() instead.",
        )
        return []

    async def clear_conversation(self, conversation_id: uuid.UUID) -> None:
        """
        Clear history for a conversation.

        Delegates to MemoryService for persistent deletion.

        Args:
            conversation_id: The conversation UUID to clear.
        """
        await self._memory.short_term.clear_conversation(str(conversation_id))
