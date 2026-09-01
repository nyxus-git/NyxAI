#!/usr/bin/env python3
"""
scripts/voice_chat.py

NyxAI Push-to-Talk CLI

A standalone voice chat script that lets you speak to NyxAI directly
from the terminal. This is Phase 3's primary voice interface.

Usage:
    python scripts/voice_chat.py                    # companion mode
    python scripts/voice_chat.py --mode agent       # agent mode (tools enabled)
    python scripts/voice_chat.py --whisper small    # use small Whisper model
    python scripts/voice_chat.py --no-tts           # disable TTS (text only)

How it works:
    1. Press Enter → microphone recording starts
    2. Press Enter again → recording stops, processing begins
    3. Whisper transcribes your speech
    4. NyxAI responds (text shown + optionally spoken aloud)
    5. Repeat (Ctrl+C to quit)

Requirements:
    - Ollama running: ollama serve
    - NyxAI backend running: make dev   (OR use --local for direct mode)
    - Microphone available

Notes:
    - Whisper model is loaded on first use (may take a moment)
    - CUDA is used automatically if available (RTX 4050 → very fast)
    - Hindi/Marathi speech is detected automatically
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to path (allows running from any directory)
sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NyxAI Push-to-Talk Voice Chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["companion", "agent"],
        default="agent",
        help="Chat mode. 'agent' enables tools (battery, apps, etc). Default: agent",
    )
    parser.add_argument(
        "--whisper",
        default="small",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size. 'small' is recommended. Default: small",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        choices=["cuda", "cpu"],
        help="Device for Whisper. 'cuda' uses RTX 4050. Default: cuda",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable text-to-speech output (text only mode)",
    )
    parser.add_argument(
        "--voice",
        default="af_heart",
        help="Kokoro TTS voice name. Default: af_heart",
    )
    return parser.parse_args()


def print_banner() -> None:
    print("""
╔═══════════════════════════════════════════════════════════╗
║              NyxAI — Push-to-Talk Voice Chat              ║
║                                                           ║
║  Press Enter to record, Enter again to stop               ║
║  Ctrl+C to quit                                           ║
╚═══════════════════════════════════════════════════════════╝
""")


async def run_voice_chat(args: argparse.Namespace) -> None:
    """Main voice chat loop."""
    from core.agent.schemas import AgentMode
    from voice.stt.transcriber import WhisperTranscriber
    from voice.tts.speaker import NyxTTSSpeaker
    from voice.wakeword.listener import PushToTalkListener

    print_banner()

    # ── Initialize components ──────────────────────────────────────────────────
    print(f"🤖 Mode: {args.mode.upper()}")
    print(f"🧠 Whisper: {args.whisper} on {args.device}")
    print(f"🔊 TTS: {'disabled (text only)' if args.no_tts else args.voice}")
    print()

    print("⚙️  Initializing... (Whisper loads on first use, ~5 seconds)")

    transcriber = WhisperTranscriber(
        model=args.whisper,
        device=args.device,
        compute_type="float16" if args.device == "cuda" else "int8",
    )

    tts_speaker: NyxTTSSpeaker | None = None
    if not args.no_tts:
        tts_speaker = NyxTTSSpeaker(kokoro_voice=args.voice)

    listener = PushToTalkListener(sample_rate=16000, channels=1)

    # ── Initialize API connection ──────────────────────────────────────────────
    # Import ChatService and LLM directly (no HTTP — direct in-process call)
    from api.app.config import get_settings
    from api.app.services.chat_service import ChatService
    from core.agent.agent import NyxAgent
    from core.agent.tool_registry import build_default_registry
    from core.brain.providers.ollama import OllamaProvider

    settings = get_settings()

    llm_provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout,
    )

    tool_registry = build_default_registry()
    agent = NyxAgent(llm_provider=llm_provider, tool_registry=tool_registry)
    chat_service = ChatService(llm_provider=llm_provider, agent=agent)

    agent_mode = AgentMode(args.mode)
    conversation_id: uuid.UUID | None = None

    print(f"✅ Ready! Ollama model: {settings.ollama_model}")
    print("─" * 60)

    # ── Main loop ──────────────────────────────────────────────────────────────
    turn = 0
    while True:
        try:
            turn += 1
            print(f"\n[Turn {turn}]")

            # Record audio
            audio_bytes = listener.record_until_keypress()

            if not audio_bytes:
                print("⚠️  No audio captured. Try again.")
                continue

            # Transcribe
            print("🔍 Transcribing...")
            result = transcriber.transcribe(audio_bytes)

            if result.is_empty:
                print("⚠️  No speech detected. Try speaking more clearly.")
                continue

            lang_emoji = {"en": "🇬🇧", "hi": "🇮🇳", "mr": "🇮🇳"}.get(result.language, "🌐")
            print(f"\n{lang_emoji} You ({result.language}, {result.language_probability:.0%}): {result.text}")

            # Chat
            print("💭 NyxAI is thinking...")
            response_text, conversation_id, tool_used, tool_result = await chat_service.chat(
                message=result.text,
                conversation_id=conversation_id,
                mode=agent_mode,
            )

            print(f"\n🤖 NyxAI: {response_text}")

            if tool_used:
                print(f"   🔧 Tool used: {tool_used}")
                if tool_result:
                    # Show key data from tool result
                    simplified = {k: v for k, v in tool_result.items() if k != "status"}
                    if simplified:
                        print(f"   📊 Result: {simplified}")

            # Speak response
            if tts_speaker and not args.no_tts:
                print("🔊 Speaking...")
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: tts_speaker.speak(response_text, language=result.language),
                    )
                except Exception as e:
                    print(f"⚠️  TTS error: {e}")

            print("─" * 60)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Closing NyxAI voice chat.")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("   Continuing...")
            continue

    # Cleanup
    await llm_provider.close()


def main() -> None:
    args = parse_args()
    asyncio.run(run_voice_chat(args))


if __name__ == "__main__":
    main()
