"""
api/app/schemas/voice.py

Pydantic schemas and message types for the /voice WebSocket endpoint.

The WebSocket protocol uses JSON messages in both directions.

Client → Server:
  { "type": "audio", "data": "<base64-encoded WAV bytes>", "mode": "agent" }
  { "type": "ping" }

Server → Client:
  { "type": "transcript", "text": "What's my battery?" }
  { "type": "thinking" }   ← Avatar state: processing
  { "type": "response", "text": "Your battery is...", "audio": "<base64 WAV>" }
  { "type": "speaking" }   ← Avatar state: playing audio
  { "type": "idle" }       ← Avatar state: waiting for input
  { "type": "error", "message": "..." }
"""

from typing import Any, Literal
from pydantic import BaseModel


class VoiceAudioMessage(BaseModel):
    """Client → Server: Send audio for transcription + response."""

    type: Literal["audio"] = "audio"
    data: str  # Base64-encoded WAV bytes
    mode: Literal["companion", "agent"] = "companion"
    conversation_id: str | None = None


class VoicePingMessage(BaseModel):
    """Client → Server: Keep-alive ping."""

    type: Literal["ping"] = "ping"


class VoiceTranscriptMessage(BaseModel):
    """Server → Client: Transcription of the user's speech."""

    type: Literal["transcript"] = "transcript"
    text: str
    language: str
    language_probability: float


class VoiceThinkingMessage(BaseModel):
    """Server → Client: Signal that NyxAI is processing."""

    type: Literal["thinking"] = "thinking"


class VoiceResponseMessage(BaseModel):
    """Server → Client: NyxAI's spoken response."""

    type: Literal["response"] = "response"
    text: str                    # NyxAI's text response
    audio: str                   # Base64-encoded WAV audio bytes
    tool_used: str | None = None
    tool_result: dict[str, Any] | None = None
    conversation_id: str | None = None


class VoiceSpeakingMessage(BaseModel):
    """Server → Client: Signal that audio is playing."""

    type: Literal["speaking"] = "speaking"


class VoiceIdleMessage(BaseModel):
    """Server → Client: Signal that NyxAI is idle, waiting for input."""

    type: Literal["idle"] = "idle"


class VoiceErrorMessage(BaseModel):
    """Server → Client: Error notification."""

    type: Literal["error"] = "error"
    message: str
    code: str = "unknown_error"
