"""
voice/tts
Text-to-speech module for NyxAI.
"""

from voice.tts.speaker import (
    EdgeTTSSpeaker,
    KokoroSpeaker,
    MithiSpeaker,
    NyxTTSSpeaker,
    Pyttsx3Speaker,
    TTSProvider,
    cancel_current_playback,
    clean_tts_text,
    is_playback_active,
    play_audio_array,
    play_wav_bytes,
)

__all__ = [
    "TTSProvider",
    "KokoroSpeaker",
    "Pyttsx3Speaker",
    "EdgeTTSSpeaker",
    "MithiSpeaker",
    "NyxTTSSpeaker",
    "clean_tts_text",
    "cancel_current_playback",
    "is_playback_active",
    "play_audio_array",
    "play_wav_bytes",
]

