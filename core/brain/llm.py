"""
core/brain/llm.py

Abstract base class for all LLM providers in NyxAI.

Every LLM provider (Ollama, future OpenAI, vLLM, etc.) MUST implement
this interface. This ensures that the rest of the system never depends
on a specific LLM implementation — only on this contract.

Swapping the LLM provider requires zero changes to the API layer,
agent layer, or any other consumer of this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator


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
