"""
api/app/services/chat_service.py

Chat orchestration service for NyxAI.

This service sits between the API router and the LLM provider.
It is responsible for:
  - Managing in-memory conversation history per session
  - Building the message list (system prompt + history + new message)
  - Calling the LLM provider
  - Returning the response

In Phase 5, this service will be extended to:
  - Persist conversations to SQLite
  - Retrieve relevant long-term memories
  - Inject retrieved memory into the message context

Design: The service holds a reference to the LLMProvider (injected via
the app lifespan). This makes it straightforward to test with a mock provider.
"""

import uuid
from collections import defaultdict

from core.brain.llm import LLMProvider, Message, MessageRole
from core.brain.prompts import get_system_prompt
from core.logging import get_logger

logger = get_logger(__name__)

# Maximum number of conversation turns to retain in memory per session.
# One turn = one user message + one assistant response.
# Keeping this bounded prevents unbounded memory growth and context overflow.
MAX_HISTORY_TURNS = 20


class ChatService:
    """
    Manages conversational interactions with the LLM.

    Maintains in-memory conversation history per conversation_id.
    This is Phase 1 — persistence will be added in Phase 5.

    Args:
        llm_provider: Any LLMProvider implementation. Injected at startup.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider
        # conversation_id (str) → list of Message objects
        self._conversations: dict[str, list[Message]] = defaultdict(list)

        logger.info(
            "chat_service_initialized",
            provider=type(llm_provider).__name__,
            model=llm_provider.get_model_name(),
        )

    async def chat(
        self,
        message: str,
        conversation_id: uuid.UUID | None = None,
    ) -> tuple[str, uuid.UUID]:
        """
        Process a user message and return NyxAI's response.

        Args:
            message: The user's input text.
            conversation_id: Optional UUID to continue an existing conversation.
                             If None, a new conversation is started.

        Returns:
            A tuple of (response_text, conversation_id).
            The conversation_id may be newly generated if none was provided.
        """
        # Generate a new ID if this is a fresh conversation
        if conversation_id is None:
            conversation_id = uuid.uuid4()
            logger.info("chat_new_conversation", conversation_id=str(conversation_id))
        else:
            logger.info(
                "chat_continue_conversation",
                conversation_id=str(conversation_id),
                history_length=len(self._conversations[str(conversation_id)]),
            )

        conv_key = str(conversation_id)

        # Build the message list for this request:
        # [system_prompt] + [conversation_history] + [new_user_message]
        system_message = Message(
            role=MessageRole.SYSTEM,
            content=get_system_prompt(compact=False),
        )
        user_message = Message(role=MessageRole.USER, content=message)

        # Retrieve existing history for this conversation
        history = self._conversations[conv_key]

        # Construct full message list to send to the LLM
        messages_to_send = [system_message] + history + [user_message]

        logger.debug(
            "chat_sending_to_llm",
            conversation_id=conv_key,
            total_messages=len(messages_to_send),
        )

        # Call the LLM provider
        llm_response = await self._llm.chat(messages_to_send)

        # Update conversation history
        history.append(user_message)
        history.append(
            Message(role=MessageRole.ASSISTANT, content=llm_response.content)
        )

        # Trim history to prevent unbounded growth
        # Keep the last MAX_HISTORY_TURNS * 2 messages (user + assistant pairs)
        max_messages = MAX_HISTORY_TURNS * 2
        if len(history) > max_messages:
            trimmed = len(history) - max_messages
            self._conversations[conv_key] = history[trimmed:]
            logger.debug(
                "chat_history_trimmed",
                conversation_id=conv_key,
                trimmed_messages=trimmed,
            )

        logger.info(
            "chat_complete",
            conversation_id=conv_key,
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        return llm_response.content, conversation_id

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
