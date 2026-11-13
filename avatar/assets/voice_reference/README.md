# NyxAI Custom Voice Reference (Voice Cloning)

You can clone any girl's voice and have NyxAI speak in that exact voice!

## How to use:
1. Record or obtain a clean 5 to 15 second `.wav` audio clip of the girl speaking (without background music or echo).
2. Save the file in this folder as:
   `avatar/assets/voice_reference/girl_voice.wav`
   (or set `NYXAI_VOICE_CLONE_SAMPLE=/path/to/your/audio.wav` in your `.env` file).

## Supported Open-Source Voice Cloning Engines:
- **XTTS-v2** (`coqui-tts` / `TTS`): Native support for zero-shot cloning in Hindi, English, and 15+ languages.
- **F5-TTS / E2-TTS**: SOTA fast flow-matching voice cloner.
- **CosyVoice-2** (Alibaba): Multilingual zero-shot voice cloner.

## Default Female Neural Voices (Active Now):
- **Hindi**: `hi-IN-SwaraNeural` (Natural, expressive Indian female voice)
- **English**: `af_heart` (Kokoro) / `en-IN-NeerjaExpressiveNeural` / `en-US-JennyNeural`
- **Marathi**: `mr-IN-AarohiNeural`

