"""
api/app/routers/voice.py

WebSocket voice endpoint for NyxAI.

GET /voice (WebSocket upgrade)

This endpoint enables real-time voice conversation:
  1. Client sends base64-encoded WAV audio
  2. Server transcribes with faster-whisper
  3. Server sends transcript event
  4. Server routes to ChatService (companion or agent mode)
  5. Server sends thinking event
  6. Server synthesizes response with Kokoro/pyttsx3
  7. Server sends response event with text + base64 audio
  8. Client plays audio, avatar enters speaking state
  9. Server sends idle event

Avatar state machine events:
  idle → [user sends audio] → thinking → speaking → idle

This WebSocket protocol is designed for the Companion UI .
"""

import asyncio
import base64
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status

from api.app.schemas.voice import (
    VoiceAudioMessage,
    VoiceErrorMessage,
    VoiceIdleMessage,
    VoiceResponseMessage,
    VoiceSpeakingMessage,
    VoiceThinkingMessage,
    VoiceTranscriptMessage,
)
from api.app.services.avatar_service import (
    detect_response_emotion,
    synthesize_speech_with_visemes,
)
from core.agent.schemas import AgentMode
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Voice"])


async def _send(ws: WebSocket, data: dict) -> None:
    """Send a JSON message to the WebSocket client."""
    await ws.send_text(json.dumps(data))


async def _run_voice_turn(
    *,
    audio_bytes: bytes,
    mode_str: str,
    conversation_id: uuid.UUID | None,
    voice_override: str | None,
    auto_approve: bool,
    chat_service: Any,
    transcriber: Any,
    tts_speaker: Any,
) -> dict[str, Any]:
    """Execute STT -> Chat/Agent -> TTS + Viseme pipeline for one voice turn."""
    if transcriber is None:
        raise RuntimeError("STT transcriber not initialized. Check server startup.")

    agent_mode = AgentMode(mode_str) if mode_str in ("companion", "agent") else AgentMode.COMPANION
    loop = asyncio.get_running_loop()

    stt_result = await loop.run_in_executor(None, lambda: transcriber.transcribe(audio_bytes))
    if stt_result.is_empty:
        return {"empty": True}

    response_text, next_conv_id, tool_used, tool_result = await chat_service.chat(
        message=stt_result.text,
        conversation_id=conversation_id,
        mode=agent_mode,
        auto_approve=auto_approve,
    )

    audio_out_b64 = ""
    visemes: list[dict[str, Any]] = []
    if tts_speaker is not None:
        try:
            audio_out_b64, visemes = await synthesize_speech_with_visemes(
                tts_speaker=tts_speaker,
                text=response_text,
                voice=voice_override,
            )
            audio_out_b64 = audio_out_b64 or ""
        except Exception as e:
            logger.error("voice_tts_error", error=str(e))

    emotion = detect_response_emotion(
        response_text,
        tool_used=tool_used,
        tool_result=tool_result,
    )

    return {
        "empty": False,
        "transcript": stt_result.text,
        "language": stt_result.language,
        "language_probability": stt_result.language_probability,
        "text": response_text,
        "audio": audio_out_b64,
        "visemes": visemes,
        "emotion": emotion,
        "tool_used": tool_used,
        "tool_result": tool_result,
        "conversation_id": str(next_conv_id) if next_conv_id else None,
    }


@router.post("/voice/ask", summary="HTTP fallback endpoint for voice question")
async def voice_ask(request: Request, body: VoiceAudioMessage) -> dict[str, Any]:
    """Process base64 audio via HTTP when WebSocket is temporarily unavailable."""
    try:
        audio_bytes = base64.b64decode(body.data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "decode_error", "message": f"Invalid base64 audio: {e}"},
        ) from e

    conv_id: uuid.UUID | None = None
    if body.conversation_id:
        try:
            conv_id = uuid.UUID(body.conversation_id)
        except ValueError:
            conv_id = None

    chat_service = request.app.state.chat_service
    transcriber = getattr(request.app.state, "transcriber", None)
    tts_speaker = getattr(request.app.state, "tts_speaker", None)

    turn = await _run_voice_turn(
        audio_bytes=audio_bytes,
        mode_str=body.mode,
        conversation_id=conv_id,
        voice_override=body.voice,
        auto_approve=body.auto_approve,
        chat_service=chat_service,
        transcriber=transcriber,
        tts_speaker=tts_speaker,
    )
    if turn["empty"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "empty_transcript", "message": "No speech detected in the audio."},
        )
    return turn


@router.websocket("/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time voice conversation with NyxAI.

    Protocol:
      Client → Server: { "type": "audio", "data": "<base64>", "mode": "agent" }
      Server → Client: (multiple events as the pipeline progresses)

    Connection lifecycle:
      - Client connects → Server accepts
      - Client sends audio → Server processes → Server responds
      - Repeat until client disconnects

    Avatar state events sent: thinking → [response + audio] → speaking → idle
    """
    await websocket.accept()
    client_id = str(uuid.uuid4())[:8]
    logger.info("voice_ws_connected", client_id=client_id)

    # Get services from app state
    chat_service = websocket.app.state.chat_service
    transcriber = getattr(websocket.app.state, "transcriber", None)
    tts_speaker = getattr(websocket.app.state, "tts_speaker", None)

    # Track conversation_id across turns
    conversation_id: uuid.UUID | None = None

    try:
        # Signal ready
        await _send(websocket, VoiceIdleMessage().model_dump())

        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send(
                    websocket,
                    VoiceErrorMessage(
                        message="Invalid JSON received.",
                        code="invalid_json",
                    ).model_dump(),
                )
                continue

            msg_type = message.get("type", "")

            # ── Ping / keep-alive
            if msg_type == "ping":
                await _send(websocket, {"type": "pong"})
                continue

            # ── Audio message — main pipeline
            if msg_type != "audio":
                await _send(
                    websocket,
                    VoiceErrorMessage(
                        message=f"Unknown message type: '{msg_type}'",
                        code="unknown_type",
                    ).model_dump(),
                )
                continue

            # Decode base64 audio
            try:
                audio_b64 = message.get("data", "")
                audio_bytes = base64.b64decode(audio_b64)
            except Exception as e:
                await _send(
                    websocket,
                    VoiceErrorMessage(
                        message=f"Failed to decode audio: {e}",
                        code="decode_error",
                    ).model_dump(),
                )
                continue

            mode_str = message.get("mode", "companion")
            agent_mode = AgentMode(mode_str) if mode_str in ("companion", "agent") else AgentMode.COMPANION
            auto_approve = bool(message.get("auto_approve", False))

            # Use provided conversation_id or maintain across turns
            msg_conv_id = message.get("conversation_id")
            if msg_conv_id:
                try:
                    conversation_id = uuid.UUID(msg_conv_id)
                except ValueError:
                    pass

            logger.info(
                "voice_ws_audio_received",
                client_id=client_id,
                audio_size_bytes=len(audio_bytes),
                mode=mode_str,
            )

            # Signal thinking immediately so the avatar animates during STT + LLM
            await _send(websocket, VoiceThinkingMessage().model_dump())

            # ── Step 1: Transcribe
            try:
                if transcriber is None:
                    raise RuntimeError("STT transcriber not initialized. Check server startup.")

                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: transcriber.transcribe(audio_bytes),
                )

            except Exception as e:
                logger.error("voice_ws_transcription_error", client_id=client_id, error=str(e))
                await _send(
                    websocket,
                    VoiceErrorMessage(
                        message=f"Transcription failed: {str(e)[:100]}",
                        code="stt_error",
                    ).model_dump(),
                )
                await _send(websocket, VoiceIdleMessage().model_dump())
                continue

            if result.is_empty:
                logger.info("voice_ws_empty_transcript", client_id=client_id)
                await _send(
                    websocket,
                    VoiceErrorMessage(
                        message="No speech detected in the audio. Try speaking closer to the mic.",
                        code="empty_transcript",
                    ).model_dump(),
                )
                await _send(websocket, VoiceIdleMessage().model_dump())
                continue

            # Send transcript to client
            await _send(
                websocket,
                VoiceTranscriptMessage(
                    text=result.text,
                    language=result.language,
                    language_probability=result.language_probability,
                ).model_dump(),
            )

            # ── Step 2: Think (LLM/Agent)
            try:
                response_text, conversation_id, tool_used, tool_result = await chat_service.chat(
                    message=result.text,
                    conversation_id=conversation_id,
                    mode=agent_mode,
                    auto_approve=auto_approve,
                )
            except Exception as e:
                logger.error("voice_ws_chat_error", client_id=client_id, error=str(e))
                await _send(
                    websocket,
                    VoiceErrorMessage(
                        message=f"Chat processing failed: {str(e)[:100]}",
                        code="chat_error",
                    ).model_dump(),
                )
                await _send(websocket, VoiceIdleMessage().model_dump())
                continue

            # ── Step 3: Synthesize response audio & lip-sync visemes
            audio_out_b64 = ""
            visemes: list[dict[str, Any]] = []
            voice_override = message.get("voice")
            try:
                if tts_speaker is None:
                    raise RuntimeError("TTS speaker not initialized. Check server startup.")

                audio_out_b64, visemes = await synthesize_speech_with_visemes(
                    tts_speaker=tts_speaker,
                    text=response_text,
                    voice=voice_override,
                )
                audio_out_b64 = audio_out_b64 or ""

            except Exception as e:
                logger.error("voice_ws_tts_error", client_id=client_id, error=str(e))
                # Send response text even if TTS fails — graceful degradation
                audio_out_b64 = ""

            emotion = detect_response_emotion(
                response_text,
                tool_used=tool_used,
                tool_result=tool_result,
            )

            # ── Step 4: Send response (client handles speaking -> idle on audio end)
            await _send(
                websocket,
                VoiceResponseMessage(
                    text=response_text,
                    audio=audio_out_b64,
                    visemes=visemes,
                    emotion=emotion,
                    tool_used=tool_used,
                    tool_result=tool_result,
                    conversation_id=str(conversation_id) if conversation_id else None,
                ).model_dump(),
            )

            if audio_out_b64:
                await _send(websocket, VoiceSpeakingMessage().model_dump())
            else:
                await _send(websocket, VoiceIdleMessage().model_dump())

            logger.info(
                "voice_ws_turn_complete",
                client_id=client_id,
                transcript=result.text[:60],
                response_preview=response_text[:60],
                tool_used=tool_used,
            )

    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", client_id=client_id)
    except Exception as e:
        logger.exception("voice_ws_unexpected_error", client_id=client_id, error=str(e))
        try:
            await _send(
                websocket,
                VoiceErrorMessage(
                    message="An unexpected server error occurred.",
                    code="server_error",
                ).model_dump(),
            )
        except Exception:
            pass
