#!/usr/bin/env python3
"""
apps/desktop/main.py

NyxAI Desktop Integration & Companion Controller.

Provides desktop automation and Wayland/Hyprland window controls:
  1. Window Toggling (SUPER + J): Focuses, minimizes, or launches the Companion UI.
  2. Push-To-Talk (SUPER + SPACE): Triggers audio recording and interacts with the voice pipeline.
  3. Desktop Daemon: Persistent user-space agent service monitoring backend health and handling IPC events.

Usage:
    python apps/desktop/main.py toggle-ui
    python apps/desktop/main.py ptt
    python apps/desktop/main.py daemon
    python apps/desktop/main.py status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.logging import configure_logging, get_logger

logger = get_logger(__name__)

BACKEND_URL = os.getenv("NYXAI_BACKEND_URL", "http://127.0.0.1:8000")
UI_URL = os.getenv("NYXAI_UI_URL", "http://127.0.0.1:5173")
SOCKET_PATH = Path(os.getenv("NYXAI_SOCKET_PATH", "/tmp/nyxai-desktop.sock"))


def is_hyprland() -> bool:
    """Check if currently running under Hyprland."""
    return bool(os.getenv("HYPRLAND_INSTANCE_SIGNATURE")) and shutil.which("hyprctl") is not None


def find_hyprland_window() -> dict[str, Any] | None:
    """Search for existing NyxAI companion window in Hyprland client list."""
    if not is_hyprland():
        return None

    try:
        proc = subprocess.run(
            ["hyprctl", "clients", "-j"],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        clients = json.loads(proc.stdout)
        for client in clients:
            title = client.get("title", "").lower()
            initial_title = client.get("initialTitle", "").lower()
            cls = client.get("class", "").lower()
            if "nyxai" in title or "nyxai" in initial_title or "nyxai" in cls or "5173" in title:
                return client
    except Exception as e:
        logger.warning("hyprctl_client_search_failed", error=str(e))

    return None


def toggle_ui() -> bool:
    """
    Toggle or focus the NyxAI Companion UI.
    If the window exists in Hyprland, focuses it. If already focused, toggles workspace.
    If not running, launches it in application mode.
    """
    logger.info("toggle_ui_requested")

    if is_hyprland():
        window = find_hyprland_window()
        if window:
            address = window.get("address")
            focus_history = window.get("focusHistoryID", -1)
            # If currently focused (focusHistoryID == 0), minimize/move or toggle special
            try:
                if focus_history == 0:
                    logger.info("companion_window_already_focused_toggling_away")
                    # Toggle away or move to special workspace
                    subprocess.run(["hyprctl", "dispatch", "movetoworkspacesilent", "special:nyxai"], check=True, timeout=3)
                else:
                    logger.info("focusing_companion_window", address=address)
                    subprocess.run(["hyprctl", "dispatch", "focuswindow", f"address:{address}"], check=True, timeout=3)
                return True
            except Exception as e:
                logger.warning("hyprctl_dispatch_failed", error=str(e))

    # If window is not open or not in Hyprland, launch browser in app mode
    browsers = [
        ("google-chrome-stable", ["--app=" + UI_URL, "--class=nyxai-companion"]),
        ("google-chrome", ["--app=" + UI_URL, "--class=nyxai-companion"]),
        ("chromium", ["--app=" + UI_URL, "--class=nyxai-companion"]),
        ("brave", ["--app=" + UI_URL, "--class=nyxai-companion"]),
        ("firefox", ["--new-window", UI_URL]),
    ]

    for bin_name, args in browsers:
        if shutil.which(bin_name):
            logger.info("launching_companion_browser", browser=bin_name, url=UI_URL)
            subprocess.Popen([bin_name] + args)
            return True

    # Fallback to xdg-open
    if shutil.which("xdg-open"):
        logger.info("launching_companion_fallback_xdg_open", url=UI_URL)
        subprocess.Popen(["xdg-open", UI_URL])
        return True

    logger.error("no_suitable_browser_found")
    return False


async def run_ptt() -> None:
    """Trigger Push-To-Talk voice interaction directly via terminal/desktop shortcut."""
    from voice.wakeword.listener import PushToTalkListener
    from voice.tts.speaker import NyxTTSSpeaker

    print("\n[NyxAI PTT] Listening... (Press Enter or wait for speech)")
    listener = PushToTalkListener(sample_rate=16000)

    try:
        # Run record in thread to prevent blocking event loop
        loop = asyncio.get_running_loop()
        wav_bytes = await loop.run_in_executor(None, listener.record_until_keypress)

        if not wav_bytes:
            print("[NyxAI PTT] No audio captured.")
            return

        print(f"[NyxAI PTT] Captured {len(wav_bytes)} bytes. Processing...")

        # Transcribe audio using backend STT or local faster-whisper
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{BACKEND_URL}/health")
            if resp.status_code != 200:
                print(f"[NyxAI PTT] Backend service not ready: {resp.status_code}")
                return

        # Use WhisperTranscriber directly
        from voice.stt.transcriber import WhisperTranscriber
        transcriber = WhisperTranscriber(model="small")
        result = transcriber.transcribe(wav_bytes)

        if not result.text.strip():
            print("[NyxAI PTT] Speech not recognized.")
            return

        print(f"\nUser: {result.text} (lang={result.language})")

        # Query backend chat
        async with httpx.AsyncClient(timeout=60.0) as client:
            chat_resp = await client.post(
                f"{BACKEND_URL}/chat",
                json={"message": result.text, "mode": "agent"},
            )
            chat_data = chat_resp.json()
            reply = chat_data.get("reply", "")
            print(f"\nNyxAI: {reply}\n")

            # Speak response with correct language routing
            speaker = NyxTTSSpeaker()
            speaker.speak(reply, language=result.language)

    except Exception as e:
        logger.error("ptt_execution_failed", error=str(e))
        print(f"[NyxAI PTT Error]: {e}")


async def check_status() -> int:
    """Check status of NyxAI core backend, UI, and audio subsystems."""
    print("========================================")
    print("   NyxAI Persistent System Status       ")
    print("========================================")

    all_healthy = True

    # 1. Core Backend
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{BACKEND_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                print(f"[✓] Core Backend: RUNNING ({BACKEND_URL})")
                print(f"    Status: {data.get('status')}")
                llm = data.get("llm", {})
                print(f"    LLM: {llm.get('provider')} | model={llm.get('model')} | ready={llm.get('healthy')}")
            else:
                print(f"[✗] Core Backend: Responded with HTTP {resp.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"[✗] Core Backend: NOT REACHABLE ({e})")
            all_healthy = False

    # 2. Companion UI
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            resp = await client.get(UI_URL)
            if resp.status_code in (200, 304):
                print(f"[✓] Companion UI: RUNNING ({UI_URL})")
            else:
                print(f"[?] Companion UI: HTTP {resp.status_code}")
        except Exception:
            print(f"[-] Companion UI: Offline or not serving at {UI_URL}")

    # 3. Environment & Window Manager
    wm = "Hyprland (Wayland)" if is_hyprland() else os.getenv("XDG_CURRENT_DESKTOP", "Unknown")
    print(f"[i] Desktop Environment: {wm}")
    print(f"[i] Socket IPC Path: {SOCKET_PATH}")

    print("========================================")
    return 0 if all_healthy else 1


async def run_daemon() -> None:
    """
    Run persistent desktop daemon.
    Listens for IPC commands on Unix Domain Socket (/tmp/nyxai-desktop.sock).
    """
    configure_logging("INFO")
    logger.info("nyxai_desktop_daemon_starting", socket=str(SOCKET_PATH))

    if SOCKET_PATH.exists():
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        logger.info("daemon_received_stop_signal")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _sig_handler)

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await reader.readline()
            command = data.decode().strip()
            logger.info("daemon_command_received", command=command)

            response = {"status": "ok", "command": command}
            if command == "toggle-ui":
                success = toggle_ui()
                response["success"] = success
            elif command == "status":
                response["running"] = True
            else:
                response["error"] = f"Unknown command: {command}"

            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
        except Exception as err:
            logger.warning("daemon_client_handling_error", error=str(err))
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_unix_server(handle_client, path=str(SOCKET_PATH))
    logger.info("daemon_listening_on_socket", path=str(SOCKET_PATH))

    try:
        await stop_event.wait()
    finally:
        server.close()
        await server.wait_closed()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        logger.info("daemon_stopped_cleanly")


def main() -> None:
    parser = argparse.ArgumentParser(description="NyxAI Desktop Integration & Companion Controller")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    subparsers.add_parser("toggle-ui", help="Toggle or focus Companion UI (SUPER+J)")
    subparsers.add_parser("ptt", help="Trigger push-to-talk voice input (SUPER+SPACE)")
    subparsers.add_parser("status", help="Check status of all NyxAI services")
    subparsers.add_parser("daemon", help="Run desktop daemon for IPC/shortcuts")

    args = parser.parse_args()

    if args.command == "toggle-ui":
        success = toggle_ui()
        sys.exit(0 if success else 1)
    elif args.command == "ptt":
        asyncio.run(run_ptt())
    elif args.command == "status":
        code = asyncio.run(check_status())
        sys.exit(code)
    elif args.command == "daemon":
        asyncio.run(run_daemon())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
