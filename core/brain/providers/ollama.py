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
  - Implements chat_with_tools() using Ollama's native tool calling.
"""

import json
from typing import AsyncGenerator

import httpx

from core.agent.schemas import ToolCall
from core.brain.llm import (
    LLMConnectionError,
    LLMModelError,
    LLMProvider,
    LLMResponse,
    LLMResponseWithTools,
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
    ) -> AsyncGenerator[str, None]:
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

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        temperature: float = 0.5,
    ) -> LLMResponseWithTools:
        """
        Send a conversation to Ollama with available tools for native tool calling.

        Uses Ollama's /api/chat endpoint with the 'tools' parameter.
        The model will either:
          - Return a text response (message.tool_calls is absent/empty)
          - Return a tool call decision (message.tool_calls contains one or more calls)

        Ollama tool call response shape:
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_battery_status",
                            "arguments": {}
                        }
                    }
                ]
            },
            "done": true
        }

        Args:
            messages: Ordered conversation messages.
            tools: Tool definitions in Ollama-compatible JSON format.
            temperature: Lower temperature (default 0.5) for more deterministic
                         tool selection vs. general conversation.

        Returns:
            LLMResponseWithTools with tool_calls populated if the LLM chose a tool,
            or content populated if it chose to respond directly.

        Raises:
            LLMConnectionError: If Ollama is not reachable.
            LLMModelError: If the model is not available.
            LLMTimeoutError: If the request times out.
        """
        payload: dict = {
            "model": self._model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": tools,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        logger.debug(
            "ollama_chat_with_tools_request",
            model=self._model,
            message_count=len(messages),
            tool_count=len(tools),
        )

        try:
            client = self._get_client()
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()

        except httpx.ConnectError as e:
            logger.error("ollama_tool_connection_failed", error=str(e))
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Is Ollama running? Start it with: ollama serve"
            ) from e

        except httpx.TimeoutException as e:
            logger.error("ollama_tool_request_timeout", model=self._model)
            raise LLMTimeoutError(
                f"Ollama tool request timed out after {self._timeout}s."
            ) from e

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text
            if status == 404:
                logger.error("ollama_model_not_found", model=self._model)
                raise LLMModelError(
                    f"Model '{self._model}' not found. Pull it: ollama pull {self._model}"
                ) from e
            logger.error("ollama_tool_http_error", status=status, body=body[:200])
            raise LLMConnectionError(f"Ollama returned HTTP {status}: {body[:200]}") from e

        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "") or ""
        raw_tool_calls = message.get("tool_calls", []) or []

        # Parse Ollama's tool_calls format into our typed ToolCall objects
        tool_calls: list[ToolCall] = []
        for i, tc in enumerate(raw_tool_calls):
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            arguments = func.get("arguments", {})

            if not tool_name:
                logger.warning("ollama_tool_call_missing_name", index=i)
                continue

            # Ollama may return arguments as a JSON string or a dict
            if isinstance(arguments, str):
                try:
                    arguments = __import__("json").loads(arguments)
                except Exception:
                    arguments = {}

            tool_calls.append(
                ToolCall(
                    name=tool_name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                    call_id=tc.get("id"),
                )
            )

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        logger.info(
            "ollama_tool_chat_complete",
            model=self._model,
            has_tool_calls=bool(tool_calls),
            tool_names=[tc.name for tc in tool_calls],
            prompt_tokens=prompt_tokens,
        )

        return LLMResponseWithTools(
            content=content,
            model=self._model,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

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
