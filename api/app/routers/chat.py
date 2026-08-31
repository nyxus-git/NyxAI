"""
api/app/routers/chat.py

Chat endpoint router for NyxAI.

POST /chat

Accepts a user message, routes it through the ChatService to the
configured LLM provider, and returns NyxAI's response.

The router delegates all business logic to ChatService — keeping the
router thin and focused only on HTTP concerns (request parsing,
response formatting, error handling).
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from api.app.schemas.chat import ChatRequest, ChatResponse
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
        "Provide a conversation_id to continue an existing conversation."
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
        body: Validated ChatRequest with message and optional conversation_id.

    Returns:
        ChatResponse with NyxAI's reply and conversation metadata.

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
    )

    try:
        response_text, conversation_id = await chat_service.chat(
            message=body.message,
            conversation_id=body.conversation_id,
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

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        model=request.app.state.llm_provider.get_model_name(),
    )
