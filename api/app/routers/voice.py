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

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from api.app.schemas.voice import (
    VoiceErrorMessage,
    VoiceIdleMessage,
    VoiceResponseMessage,
    VoiceSpeakingMessage,
    VoiceThinkingMessage,
    VoiceTranscriptMessage,
)
from core.agent.schemas import AgentMode
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Voice"])


async def _send(ws: WebSocket, data: dict) -> None:
    """Send a JSON message to the WebSocket client."""
    await ws.send_text(json.dumps(data))


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

            # ── Step 1: Transcribe
            try:
                if transcriber is None:
                    raise RuntimeError("STT transcriber not initialized. Check server startup.")

                # Run transcription in thread pool (it's a blocking CPU/GPU call)
                loop = asyncio.get_event_loop()
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
                        message="No speech detected in the audio.",
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
            await _send(websocket, VoiceThinkingMessage().model_dump())

            try:
                response_text, conversation_id, tool_used, tool_result = await chat_service.chat(
                    message=result.text,
                    conversation_id=conversation_id,
                    mode=agent_mode,
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

            # ── Step 3: Synthesize response audio
            try:
                if tts_speaker is None:
                    raise RuntimeError("TTS speaker not initialized. Check server startup.")

                # Detect the language of the LLM's *response* (not the user's input).
                # This matters for mixed conversations: user may speak Hinglish but
                # NyxAI may respond in Devanagari Hindi — TTS must follow the response.
                from core.brain.language import detect_response_language
                response_lang = detect_response_language(response_text)

                audio_out = await loop.run_in_executor(
                    None,
                    lambda: tts_speaker.synthesize(response_text, language=response_lang),
                )
                audio_out_b64 = base64.b64encode(audio_out).decode()

            except Exception as e:
                logger.error("voice_ws_tts_error", client_id=client_id, error=str(e))
                # Send response text even if TTS fails — graceful degradation
                audio_out_b64 = ""

            # ── Step 4: Send response
            await _send(
                websocket,
                VoiceResponseMessage(
                    text=response_text,
                    audio=audio_out_b64,
                    tool_used=tool_used,
                    tool_result=tool_result,
                    conversation_id=str(conversation_id) if conversation_id else None,
                ).model_dump(),
            )

            await _send(websocket, VoiceSpeakingMessage().model_dump())

            # Brief pause to let client start playback before we signal idle
            await asyncio.sleep(0.3)
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
