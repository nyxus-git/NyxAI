"""
core/brain/llm.py

Abstract base class for all LLM providers in NyxAI.

Every LLM provider (Ollama, future OpenAI, vLLM, etc.) MUST implement
this interface. This ensures that the rest of the system never depends
on a specific LLM implementation — only on this contract.

Swapping the LLM provider requires zero changes to the API layer,
agent layer, or any other consumer of this interface.

Phase 2 additions:
  - LLMResponseWithTools: Carries both text content and tool call decisions
  - chat_with_tools(): Abstract method for LLM-native tool calling
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from core.agent.schemas import ToolCall


class MessageRole(str, Enum):
    """Chat message roles matching the OpenAI conversation format."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """
    A single message in a conversation.

    Attributes:
        role: Who sent this message (system, user, or assistant).
        content: The text content of the message.
    """

    role: MessageRole
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dict format expected by Ollama and OpenAI APIs."""
        return {"role": self.role.value, "content": self.content}


@dataclass
class LLMResponse:
    """
    Structured response from an LLM provider.

    Attributes:
        content: The generated text response.
        model: The model name that generated the response.
        prompt_tokens: Number of tokens in the input (if available).
        completion_tokens: Number of tokens in the output (if available).
        total_tokens: Total tokens used (if available).
    """

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class LLMResponseWithTools:
    """
    Response from an LLM provider when tools are available.

    When Ollama (or any provider) responds to a chat_with_tools() call,
    it either:
      a) Returns a text response directly (tool_calls is empty)
      b) Returns a tool call decision (content may be empty, tool_calls has items)

    Attributes:
        content: Text content of the response (may be empty if tool_calls is set).
        model: The model name that generated the response.
        tool_calls: List of ToolCall objects the LLM decided to execute.
                    Empty list if the LLM chose to respond directly.
        prompt_tokens: Tokens in the input.
        completion_tokens: Tokens in the output.
    """

    content: str
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        """Return True if the LLM decided to call one or more tools."""
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """
    Abstract base class that all NyxAI LLM providers must implement.

    This is the single interface through which the rest of NyxAI
    communicates with any language model. Never instantiate a concrete
    provider directly in business logic — always depend on this type.

    Example:
        provider: LLMProvider = OllamaProvider(settings)
        response = await provider.chat(messages)
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Send a list of conversation messages and receive a response.

        This is the primary method for conversational AI interactions.

        Args:
            messages: Ordered list of conversation messages including
                      system prompt, user turns, and assistant turns.
            temperature: Sampling temperature (0.0 = deterministic,
                         1.0 = creative). Default 0.7 for balanced output.
            max_tokens: Optional maximum tokens to generate. Provider
                        default is used if None.

        Returns:
            LLMResponse with generated content and token usage.

        Raises:
            LLMConnectionError: If the provider cannot be reached.
            LLMModelError: If the requested model is not available.
            LLMTimeoutError: If the request exceeds the timeout.
        """
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a response from a single plain-text prompt.

        Useful for simple, non-conversational generation tasks.

        Args:
            prompt: The input prompt string.
            temperature: Sampling temperature.
            max_tokens: Optional maximum tokens to generate.

        Returns:
            LLMResponse with generated content.
        """
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream a chat response token-by-token.

        Used for real-time UI updates and voice synthesis pipelines
        where low first-token latency matters.

        Args:
            messages: Ordered list of conversation messages.
            temperature: Sampling temperature.

        Yields:
            String chunks as they are generated.
        """
        ...

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        temperature: float = 0.7,
    ) -> LLMResponseWithTools:
        """
        Send a conversation to the LLM with a list of available tools.

        The LLM will either:
          - Return a text response (LLMResponseWithTools.tool_calls is empty)
          - Return a tool call decision (LLMResponseWithTools.tool_calls is non-empty)

        This is the primary method for agentic interactions. The tools list
        should be in Ollama-compatible format (from ToolDefinition.to_ollama_format()).

        Args:
            messages: Ordered conversation messages (system, user, assistant turns).
            tools: List of tool definitions in Ollama JSON format.
            temperature: Sampling temperature (lower = more deterministic tool selection).

        Returns:
            LLMResponseWithTools with either content or tool_calls populated.

        Raises:
            LLMConnectionError: If the provider cannot be reached.
            LLMModelError: If the requested model is not available.
            LLMTimeoutError: If the request exceeds the timeout.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify that the LLM provider is reachable and the model is loaded.

        Returns:
            True if the provider is healthy and the model is available.
            False otherwise.
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Return the current model name being used by this provider.

        Returns:
            Model name string (e.g. 'qwen2.5:3b').
        """
        ...


# ─── Provider Exceptions ───────────────────────────────────────────────────────


class LLMError(Exception):
    """Base class for all LLM provider errors."""

    pass


class LLMConnectionError(LLMError):
    """Raised when the LLM provider cannot be reached."""

    pass


class LLMModelError(LLMError):
    """Raised when the requested model is not available on the provider."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when an LLM request exceeds the configured timeout."""

    pass
