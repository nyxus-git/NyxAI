"""
api/app/services/chat_service.py

Chat orchestration service for NyxAI.

This service sits between the API router and the LLM/Agent layer.
It is responsible for:
  - Managing in-memory conversation history per session
  - Routing requests to the correct handler based on mode:
      * mode="companion" → direct LLM call (Phase 1 behavior, unchanged)
      * mode="agent"     → NyxAgent tool-calling loop (Phase 2)
  - Building the message list (system prompt + history + new message)
  - Returning the response + metadata

Phase 2 additions:
  - Accepts NyxAgent (optional) for agent mode delegation
  - Returns (response_text, conversation_id, tool_used, tool_result) tuple
  - History is shared across both companion and agent modes per conversation_id

In Phase 5, this service will be extended to persist conversations to SQLite
and inject relevant long-term memories into the context.
"""

import uuid
from collections import defaultdict
from typing import Any

from core.agent.schemas import AgentMode
from core.brain.llm import LLMProvider, Message, MessageRole
from core.brain.prompts import get_system_prompt
from core.logging import get_logger

logger = get_logger(__name__)

# Maximum number of conversation turns to retain in memory per session.
# One turn = one user message + one assistant response.
MAX_HISTORY_TURNS = 20


class ChatService:
    """
    Manages conversational interactions with the LLM (companion mode)
    and the NyxAgent (agent mode).

    Maintains in-memory conversation history per conversation_id.
    This is Phase 1/2 — persistence will be added in Phase 5.

    Args:
        llm_provider: Any LLMProvider implementation. Injected at startup.
        agent: Optional NyxAgent for tool-calling mode. If None, agent mode
               falls back to companion mode with a warning.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        agent: "Any | None" = None,
    ) -> None:
        self._llm = llm_provider
        self._agent = agent
        # conversation_id (str) → list of Message objects
        self._conversations: dict[str, list[Message]] = defaultdict(list)

        logger.info(
            "chat_service_initialized",
            provider=type(llm_provider).__name__,
            model=llm_provider.get_model_name(),
            agent_enabled=agent is not None,
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
            - response_text: NyxAI's reply
            - conversation_id: UUID (newly generated if not provided)
            - tool_used: Name of the tool called, or None
            - tool_result: Raw tool output data, or None
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
                history_length=len(self._conversations[str(conversation_id)]),
                mode=mode.value,
            )

        conv_key = str(conversation_id)
        history = self._conversations[conv_key]

        # ── Route to the correct handler ─────────────────────────────────────
        if mode == AgentMode.AGENT and self._agent is not None:
            response_text, tool_used, tool_result = await self._handle_agent(
                message=message,
                history=history,
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
                history=history,
                conv_key=conv_key,
            )

        return response_text, conversation_id, tool_used, tool_result

    async def _handle_companion(
        self,
        message: str,
        history: list[Message],
        conv_key: str,
    ) -> tuple[str, None, None]:
        """
        Handle a companion mode request — pure LLM conversation, no tools.

        Builds [system_prompt] + [history] + [user_message] and calls the LLM.
        Updates conversation history after the response.

        Returns:
            (response_text, None, None) — no tool used in companion mode.
        """
        system_message = Message(
            role=MessageRole.SYSTEM,
            content=get_system_prompt(compact=False),
        )
        user_message = Message(role=MessageRole.USER, content=message)
        messages_to_send = [system_message] + history + [user_message]

        logger.debug(
            "companion_sending_to_llm",
            conversation_id=conv_key,
            total_messages=len(messages_to_send),
        )

        llm_response = await self._llm.chat(messages_to_send)

        # Update history
        self._append_to_history(
            conv_key=conv_key,
            user_message=user_message,
            assistant_content=llm_response.content,
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
        history: list[Message],
        conv_key: str,
    ) -> tuple[str, str | None, dict | None]:
        """
        Handle an agent mode request — tool-calling agentic loop.

        Delegates to NyxAgent.run() with the current conversation history.
        Updates history with the user message and final agent response.

        Returns:
            (response_text, tool_used, tool_result)
        """
        logger.debug(
            "agent_delegating",
            conversation_id=conv_key,
            history_length=len(history),
        )

        agent_response = await self._agent.run(
            message=message,
            history=history,
        )

        user_message = Message(role=MessageRole.USER, content=message)

        # Update history with the final response
        self._append_to_history(
            conv_key=conv_key,
            user_message=user_message,
            assistant_content=agent_response.content,
        )

        logger.info(
            "agent_complete",
            conversation_id=conv_key,
            model=agent_response.model,
            tool_used=agent_response.tool_used,
            iterations=agent_response.iterations,
        )

        return agent_response.content, agent_response.tool_used, agent_response.tool_result

    def _append_to_history(
        self,
        conv_key: str,
        user_message: Message,
        assistant_content: str,
    ) -> None:
        """
        Append a user+assistant turn to history and trim if needed.

        Args:
            conv_key: Conversation key (str form of UUID).
            user_message: The user's message.
            assistant_content: The assistant's response text.
        """
        history = self._conversations[conv_key]
        history.append(user_message)
        history.append(Message(role=MessageRole.ASSISTANT, content=assistant_content))

        # Trim to prevent unbounded memory growth
        max_messages = MAX_HISTORY_TURNS * 2  # user + assistant pairs
        if len(history) > max_messages:
            trimmed = len(history) - max_messages
            self._conversations[conv_key] = history[trimmed:]
            logger.debug(
                "chat_history_trimmed",
                conversation_id=conv_key,
                trimmed_messages=trimmed,
            )

    def get_history(self, conversation_id: uuid.UUID) -> list[Message]:
        """
        Return the conversation history for a given conversation ID.

        Args:
            conversation_id: The conversation UUID.

        Returns:
            List of Message objects in chronological order.
            Returns empty list if conversation not found.
        """
        return self._conversations.get(str(conversation_id), [])

    def clear_conversation(self, conversation_id: uuid.UUID) -> None:
        """
        Delete all history for a conversation.

        Args:
            conversation_id: The conversation UUID to clear.
        """
        conv_key = str(conversation_id)
        if conv_key in self._conversations:
            del self._conversations[conv_key]
            logger.info("chat_conversation_cleared", conversation_id=conv_key)
