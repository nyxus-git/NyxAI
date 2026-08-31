"""
core/brain/providers/ollama.py

Ollama LLM provider implementation for NyxAI.

This is the concrete implementation of LLMProvider that communicates
with a locally running Ollama server via its REST API.

Architecture notes:
  - The model name is NEVER hardcoded. It is always read from settings.
  - Uses httpx.AsyncClient for non-blocking HTTP calls.
  - Implements streaming via Ollama's NDJSON streaming endpoint.
  - Provides health checks to verify both Ollama and the model are ready.
"""

import json
from typing import AsyncIterator

import httpx

from core.brain.llm import (
    LLMConnectionError,
    LLMModelError,
    LLMProvider,
    LLMResponse,
    LLMTimeoutError,
    Message,
)
from core.logging import get_logger

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """
    LLM provider implementation backed by a local Ollama server.

    The Ollama REST API docs: https://github.com/ollama/ollama/blob/main/docs/api.md

    Args:
        base_url: Ollama server base URL (e.g. 'http://localhost:11434').
        model: Model name to use (e.g. 'qwen2.5:3b'). NEVER hardcoded.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

        logger.info(
            "ollama_provider_initialized",
            base_url=self._base_url,
            model=self._model,
            timeout=self._timeout,
        )

    def _get_client(self) -> httpx.AsyncClient:
        """
        Return a shared async HTTP client, creating it if necessary.

        We use a lazy singleton pattern so the client is only created
        when first needed, and can be properly closed during shutdown.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client. Call during application shutdown."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("ollama_provider_closed")

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Send a conversation to Ollama's /api/chat endpoint.

        Uses the chat format with roles (system, user, assistant) which
        preserves conversation context properly.

        Args:
            messages: Ordered conversation messages.
            temperature: Sampling temperature (0.0–1.0).
            max_tokens: Optional token limit for the response.

        Returns:
            LLMResponse with the assistant's reply.

        Raises:
            LLMConnectionError: If Ollama is not reachable.
            LLMModelError: If the model is not available.
            LLMTimeoutError: If the request times out.
        """
        payload: dict = {
            "model": self._model,
            "messages": [msg.to_dict() for msg in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        logger.debug(
            "ollama_chat_request",
            model=self._model,
            message_count=len(messages),
            temperature=temperature,
        )

        try:
            client = self._get_client()
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()

        except httpx.ConnectError as e:
            logger.error("ollama_connection_failed", error=str(e), base_url=self._base_url)
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Is Ollama running? Start it with: ollama serve"
            ) from e

        except httpx.TimeoutException as e:
            logger.error("ollama_request_timeout", model=self._model, timeout=self._timeout)
            raise LLMTimeoutError(
                f"Ollama request timed out after {self._timeout}s. "
                f"The model may still be loading. Try again in a moment."
            ) from e

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text

            if status == 404:
                logger.error("ollama_model_not_found", model=self._model)
                raise LLMModelError(
                    f"Model '{self._model}' not found in Ollama. "
                    f"Pull it with: ollama pull {self._model}"
                ) from e

            logger.error("ollama_http_error", status=status, body=body)
            raise LLMConnectionError(f"Ollama returned HTTP {status}: {body}") from e

        data = response.json()

        # Ollama /api/chat response shape:
        # {"message": {"role": "assistant", "content": "..."}, "done": true,
        #  "prompt_eval_count": N, "eval_count": N}
        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        logger.info(
            "ollama_chat_complete",
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return LLMResponse(
            content=content,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a response from a plain-text prompt via /api/generate.

        Wraps the prompt as a single user message and uses the chat endpoint
        internally for consistency.

        Args:
            prompt: Raw prompt string.
            temperature: Sampling temperature.
            max_tokens: Optional token limit.

        Returns:
            LLMResponse with generated text.
        """
        from core.brain.llm import MessageRole

        messages = [Message(role=MessageRole.USER, content=prompt)]
        return await self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream chat response chunks from Ollama's /api/chat with stream=true.

        Ollama streams NDJSON — each line is a JSON object with a
        'message.content' field. We yield each content chunk as it arrives.

        Args:
            messages: Ordered conversation messages.
            temperature: Sampling temperature.

        Yields:
            String chunks of the response as they are generated.
        """
        payload = {
            "model": self._model,
            "messages": [msg.to_dict() for msg in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }

        logger.debug("ollama_stream_start", model=self._model)

        try:
            client = self._get_client()
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done", False):
                            logger.debug("ollama_stream_done", model=self._model)
                            break
                    except json.JSONDecodeError:
                        logger.warning("ollama_stream_invalid_json", line=line)
                        continue

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self._base_url}."
            ) from e
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("Ollama streaming request timed out.") from e

    async def health_check(self) -> bool:
        """
        Check if Ollama is running and the configured model is available.

        Makes two checks:
        1. Can we reach the Ollama server at all? (GET /api/tags)
        2. Is our configured model listed in the available models?

        Returns:
            True if Ollama is healthy and the model is available.
            False if anything is wrong (connection, model missing, etc.)
        """
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])
            available_model_names = [m.get("name", "") for m in models]

            # Ollama model names can include tags: "qwen2.5:3b"
            # We check both exact match and prefix match
            model_available = any(
                name == self._model or name.startswith(self._model.split(":")[0])
                for name in available_model_names
            )

            if model_available:
                logger.info("ollama_health_ok", model=self._model, available=True)
            else:
                logger.warning(
                    "ollama_model_not_in_list",
                    model=self._model,
                    available_models=available_model_names,
                )

            return model_available

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("ollama_health_failed", error=str(e))
            return False
        except Exception as e:
            logger.error("ollama_health_unexpected_error", error=str(e))
            return False

    def get_model_name(self) -> str:
        """Return the model name being used by this provider."""
        return self._model
