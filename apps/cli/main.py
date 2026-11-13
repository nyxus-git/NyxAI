#!/usr/bin/env python3
"""
apps/cli/main.py

NyxAI Unified Linux Command Line Interface (CLI).

Provides terminal-native access to the complete NyxAI ecosystem:
  - Direct queries:       nyx "what is my current battery level?"
  - Interactive chat:     nyx chat
  - Master routine:       nyx routine / nyx jarvis
  - System diagnostics:   nyx system
  - Hands-free listener:  nyx listen
  - Push-to-talk voice:   nyx voice
  - Desktop daemon:       nyx daemon [status|toggle-ui]

Usage:
    nyx "Check my CPU and memory"
    nyx chat
    nyx routine
    nyx system
    nyx daemon status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any
import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_URL = os.getenv("NYXAI_BACKEND_URL", "http://127.0.0.1:8000")
SOCKET_PATH = Path(os.getenv("NYXAI_SOCKET_PATH", "/tmp/nyxai-desktop.sock"))

# Terminal ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


async def query_backend_chat(prompt: str, auto_approve: bool = True) -> str:
    """Send query to running backend /chat endpoint; fallback to local agent if offline."""
    clean_p = prompt.strip()
    if not clean_p:
        return "Prompt cannot be empty."

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{BACKEND_URL}/chat",
                json={
                    "message": clean_p,
                    "mode": "agent",
                    "auto_approve": auto_approve,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response") or data.get("content") or "No response received."
            else:
                return f"{RED}Backend error ({resp.status_code}): {resp.text}{RESET}"
    except httpx.ConnectError:
        # Fallback to direct local supervisor execution
        return await query_local_fallback(clean_p)
    except Exception as e:
        return f"{RED}Execution error: {str(e)}{RESET}"


async def query_local_fallback(prompt: str) -> str:
    """Run prompt directly against local Ollama + NyxSupervisor when API server is not running."""
    try:
        from core.agent.supervisor import NyxSupervisor
        from core.agent.tool_registry import build_default_registry
        from core.brain.providers.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://127.0.0.1:11434", model="qwen2.5:3b")
        registry = build_default_registry()
        supervisor = NyxSupervisor(llm_provider=provider, tool_registry=registry)

        response = await supervisor.run(prompt, auto_approve=True)
        return response.content
    except Exception as err:
        return (
            f"{YELLOW}[API server offline at {BACKEND_URL}]{RESET}\n"
            f"{RED}Local fallback error: {str(err)}{RESET}\n"
            f"Tip: Start the NyxAI service with: make dev or nyxai-core.service"
        )


async def run_chat_repl() -> None:
    """Interactive conversational REPL in the terminal."""
    print(f"\n{CYAN}{BOLD}── NyxAI 2.0 Terminal Interface ──{RESET}")
    print(f"{DIM}Autonomous Local AI Companion & Desktop Agent (Arch/EndeavourOS){RESET}")
    print(f"{DIM}Connecting to: {BACKEND_URL} | Type 'exit' or 'quit' to end session.{RESET}\n")

    while True:
        try:
            prompt = input(f"{CYAN}{BOLD}nyx > {RESET}").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", ":q", "bye"):
                print(f"{GREEN}Goodbye! Have a great day.{RESET}")
                break

            print(f"{DIM}Thinking...{RESET}")
            reply = await query_backend_chat(prompt)
            print(f"\n{BOLD}{reply}{RESET}\n")

        except (KeyboardInterrupt, EOFError):
            print(f"\n{GREEN}Session ended.{RESET}")
            break


async def run_master_routine() -> None:
    """Trigger the one-shot Jarvis master routine."""
    print(f"\n{CYAN}{BOLD}⚡ Triggering NyxAI Master Routine (JARVIS Activation)...{RESET}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BACKEND_URL}/system/quick-action",
                json={"action": "activate_all_tasks"},
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"\n{GREEN}{BOLD}✓ Master Routine Executed Successfully!{RESET}\n")
                print(data.get("message", "Routine finished."))
            else:
                # Fallback to chat query
                reply = await query_backend_chat("activate all tasks")
                print(f"\n{BOLD}{reply}{RESET}")
    except Exception:
        reply = await query_backend_chat("activate all tasks")
        print(f"\n{BOLD}{reply}{RESET}")


async def run_system_diagnostics() -> None:
    """Print a terminal dashboard showing hardware health and agent statuses."""
    print(f"\n{CYAN}{BOLD}── NyxAI System & Swarm Diagnostics ──{RESET}\n")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BACKEND_URL}/system/telemetry")
            if resp.status_code == 200:
                data = resp.json()
                cpu = data.get("cpu", {})
                ram = data.get("ram", {})
                gpu = data.get("gpu", {})
                battery = data.get("battery", {})
                agents = data.get("agents", [])

                print(f"{BOLD}Hardware Telemetry:{RESET}")
                print(f"  • CPU Usage:     {GREEN}{cpu.get('percent', 0.0)}%{RESET} ({cpu.get('core_count', 1)} cores)")
                print(f"  • RAM Memory:    {GREEN}{ram.get('used_gb', 0.0):.1f} GB / {ram.get('total_gb', 0.0):.1f} GB{RESET} ({ram.get('percent', 0.0)}%)")
                print(f"  • GPU Model:     {GREEN}{gpu.get('name', 'N/A')}{RESET} (CUDA: {gpu.get('available', False)})")
                print(f"  • Battery:       {GREEN}{battery.get('percent', 100)}%{RESET} (Plugged: {battery.get('plugged_in', True)})")
                print(f"  • System Uptime: {data.get('uptime', 'Unknown')}\n")

                print(f"{BOLD}Active Multi-Agent Swarm ({len(agents)} agents):{RESET}")
                for ag in agents:
                    print(f"  • {CYAN}{ag.get('name', 'Agent')}{RESET}: [{GREEN}{ag.get('status', 'ready').upper()}{RESET}] — {DIM}{ag.get('role', '')}{RESET}")
                print()
                return
    except Exception as err:
        print(f"{YELLOW}Warning: Could not fetch telemetry via API ({err}). Reading local sensors...{RESET}")

    # Fallback to direct local tools
    from tools.system.system_tools import get_battery_status, get_cpu_usage, get_ram_usage
    c = get_cpu_usage()
    r = get_ram_usage()
    b = get_battery_status()
    print(f"  • CPU: {c.data.get('percent', 0)}%")
    print(f"  • RAM: {r.data.get('used_gb', 0):.1f} GB / {r.data.get('total_gb', 0):.1f} GB")
    print(f"  • Battery: {b.data.get('percent', 0)}% (Plugged: {b.data.get('plugged_in', True)})\n")


async def run_daemon_command(action: str) -> None:
    """Send IPC command to background desktop daemon."""
    if not SOCKET_PATH.exists():
        print(f"{YELLOW}Desktop daemon socket not found at {SOCKET_PATH}.{RESET}")
        print(f"Start the daemon with: {BOLD}python apps/desktop/main.py daemon --hands-free{RESET}")
        return

    try:
        reader, writer = await asyncio.open_unix_connection(str(SOCKET_PATH))
        writer.write(f"{action}\n".encode())
        await writer.drain()

        response_line = await reader.readline()
        writer.close()
        await writer.wait_closed()

        data = json.loads(response_line.decode().strip())
        print(f"{GREEN}{BOLD}Daemon Response:{RESET} {json.dumps(data, indent=2)}")
    except Exception as err:
        print(f"{RED}Failed to communicate with daemon: {err}{RESET}")


def main() -> None:
    """Main CLI entry point."""
    # Fast path: If user passes a direct conversational or task prompt, run it immediately
    subcommands = {
        "chat",
        "routine",
        "jarvis",
        "system",
        "daemon",
        "listen",
        "voice",
        "-h",
        "--help",
        "--version",
        "-v",
    }
    if len(sys.argv) > 1 and sys.argv[1] not in subcommands and not sys.argv[1].startswith("-"):
        prompt = " ".join(sys.argv[1:])
        reply = asyncio.run(query_backend_chat(prompt))
        print(f"\n{BOLD}{reply}{RESET}\n")
        return

    parser = argparse.ArgumentParser(
        prog="nyx",
        description="NyxAI 2.0 — Local AI Companion and Autonomous Linux Desktop Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="NyxAI 2.0 (Arch Linux / RTX 4050)")

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    # nyx chat
    subparsers.add_parser("chat", help="Start interactive terminal conversation REPL")

    # nyx routine / jarvis
    subparsers.add_parser("routine", help="Run composite Jarvis master routine (all tasks)")
    subparsers.add_parser("jarvis", help="Alias for 'routine'")

    # nyx system
    subparsers.add_parser("system", help="Display hardware health and multi-agent swarm telemetry")

    # nyx daemon
    daemon_parser = subparsers.add_parser("daemon", help="Control or inspect background desktop daemon")
    daemon_parser.add_argument("action", choices=["status", "toggle-ui"], default="status", nargs="?")

    # nyx listen
    subparsers.add_parser("listen", help="Run hands-free wake word listener directly in console")

    # nyx voice
    subparsers.add_parser("voice", help="Run push-to-talk voice recording session")

    args = parser.parse_args()

    if args.subcommand == "chat":
        asyncio.run(run_chat_repl())
    elif args.subcommand in ("routine", "jarvis"):
        asyncio.run(run_master_routine())
    elif args.subcommand == "system":
        asyncio.run(run_system_diagnostics())
    elif args.subcommand == "daemon":
        asyncio.run(run_daemon_command(args.action))
    elif args.subcommand == "listen":
        from apps.desktop.main import run_listen
        asyncio.run(run_listen())
    elif args.subcommand == "voice":
        from apps.desktop.main import run_ptt
        asyncio.run(run_ptt())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
