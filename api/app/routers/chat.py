"""
api/app/routers/chat.py

Chat endpoint router for NyxAI.

POST /chat

Accepts a user message, routes it through the ChatService to either:
  - Companion mode: Direct LLM conversation (mode="companion", default)
  - Agent mode: Tool-calling agentic loop (mode="agent")

Returns NyxAI's response with optional tool metadata.

The router delegates all business logic to ChatService — keeping the
router thin and focused only on HTTP concerns (request parsing,
response formatting, error handling).
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from api.app.schemas.chat import ChatRequest, ChatResponse
from core.agent.schemas import AgentMode
from core.brain.llm import LLMConnectionError, LLMModelError, LLMTimeoutError
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to NyxAI",
    description=(
        "Send a text message to NyxAI and receive a response. "
        "Supports English, Hindi, Marathi, and Hinglish. "
        "Use mode='companion' (default) for conversation, "
        "or mode='agent' to enable tool-calling (battery, apps, web search, etc)."
    ),
    responses={
        200: {"description": "NyxAI responded successfully."},
        422: {"description": "Invalid request (e.g., empty message)."},
        503: {"description": "Ollama LLM is unavailable."},
        504: {"description": "LLM request timed out."},
    },
)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Process a user message and return NyxAI's response.

    Args:
        request: FastAPI Request object (used to access app.state).
        body: Validated ChatRequest with message, optional conversation_id, and mode.

    Returns:
        ChatResponse with NyxAI's reply, conversation metadata, and optional tool info.

    Raises:
        503: If Ollama is not running or the model is unavailable.
        504: If the LLM request times out.
        500: For unexpected errors.
    """
    chat_service = request.app.state.chat_service

    # Log incoming request (truncate message for log readability)
    message_preview = body.message[:80] + "..." if len(body.message) > 80 else body.message
    logger.info(
        "chat_request",
        conversation_id=str(body.conversation_id) if body.conversation_id else "new",
        message_preview=message_preview,
        message_length=len(body.message),
        mode=body.mode,
    )

    # Convert string mode to AgentMode enum
    agent_mode = AgentMode(body.mode)

    try:
        response_text, conversation_id, tool_used, tool_result = await chat_service.chat(
            message=body.message,
            conversation_id=body.conversation_id,
            mode=agent_mode,
        )

    except LLMConnectionError as e:
        logger.error("chat_llm_connection_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "llm_unavailable",
                "message": str(e),
                "hint": "Make sure Ollama is running: ollama serve",
            },
        ) from e

    except LLMModelError as e:
        logger.error("chat_llm_model_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "model_unavailable",
                "message": str(e),
            },
        ) from e

    except LLMTimeoutError as e:
        logger.error("chat_llm_timeout", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "llm_timeout",
                "message": str(e),
                "hint": "The model may still be loading. Try again in a moment.",
            },
        ) from e

    except Exception as e:
        logger.exception("chat_unexpected_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred. Check the server logs.",
            },
        ) from e

    audio_b64 = None
    if body.tts:
        tts_speaker = getattr(request.app.state, "tts_speaker", None)
        if tts_speaker:
            try:
                import asyncio
                import base64
                from core.brain.language import detect_response_language
                loop = asyncio.get_event_loop()
                response_lang = detect_response_language(response_text)
                audio_bytes = await loop.run_in_executor(
                    None,
                    lambda: tts_speaker.synthesize(response_text, language=response_lang),
                )
                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode()
            except Exception as e:
                logger.warning("chat_tts_synthesis_failed", error=str(e))

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        model=request.app.state.llm_provider.get_model_name(),
        mode=body.mode,
        tool_used=tool_used,
        tool_result=tool_result,
        audio=audio_b64,
    )
