# NyxAI — Architecture & Technical Design

This document details the architectural design and system components of **NyxAI**, a local-first AI companion and intelligent desktop agent built for Linux (Arch / EndeavourOS / Hyprland).

---

## 1. High-Level Architecture

NyxAI operates as a modular, decoupled set of services running under the user's login session:

```
[ User Desktop / Hyprland Session ]
       │                      │
(SUPER + J)            (SUPER + SPACE)
       │                      │
       ▼                      ▼
  Companion UI           Push-To-Talk
(React/Vite :5173)    (apps/desktop/main.py)
       │                      │
       ▼ WebSocket            ▼ HTTP / WebSocket
 ┌────────────────────────────────────────────────────────┐
 │            NyxAI Core Backend (FastAPI :8000)          │
 │                                                        │
 │   Routers: /health, /chat, /memory, /voice             │
 │                                                        │
 │   ┌─────────────────┐       ┌──────────────────────┐   │
 │   │    NyxAgent     │       │    Memory Service    │   │
 │   │  Reasoning Loop │       │ (Short/Long/Episodic)│   │
 │   └────────┬────────┘       └──────────┬───────────┘   │
 │            │                           │               │
 │            ▼                           ▼               │
 │   ┌─────────────────┐       ┌──────────────────────┐   │
 │   │  Tool Registry  │       │   SQLite Database    │   │
 │   │ (Safe Execution)│       │ (data/nyx_memory.db) │   │
 │   └────────┬────────┘       └──────────────────────┘   │
 │            │                                           │
 │            ▼                                           │
 │   ┌─────────────────┐       ┌──────────────────────┐   │
 │   │ Safety Layer    │       │    Voice Engine      │   │
 │   │ CommandValidator│       │ faster-whisper + TTS │   │
 │   └─────────────────┘       └──────────────────────┘   │
 └────────────────────────────┬───────────────────────────┘
                              │
                              ▼
                 Ollama Service (qwen2.5:3b)
```

---

## 2. Startup & Persistent Lifecycle (PRD Section 27)

NyxAI runs autonomously without requiring manual `python main.py` execution:

```
Computer Login (systemd --user session)
       │
       ▼
systemd starts `nyxai-core.service`
       │
       ├──> FastAPI app starts & lifespan initializes
       ├──> SQLite schema validated & connection pool opened
       ├──> Ollama LLM provider health verified
       ├──> Tool registry & safety validators initialized
       └──> Reminder poller background loop starts
       │
       ▼
systemd starts `nyxai-ui.service`
       │
       └──> Companion UI built preview serves at http://127.0.0.1:5173
       │
       ▼
Hyprland Desktop Environment
       │
       ├──> SUPER + J: Toggles Companion UI via apps/desktop/main.py
       └──> SUPER + SPACE: Triggers Push-To-Talk speech interaction
```

---

## 3. Subsystem Breakdown

### 3.1 Core Backend (`api/`)
- **FastAPI**: Asynchronous REST and WebSocket framework.
- **Lifespan Manager**: Handles initialization and graceful teardown of SQLite pools, HTTP clients, and background tasks.
- **Routers**:
  - `/health`: Health status of backend and LLM provider.
  - `/chat`: Main conversation and agent completion endpoint.
  - `/memory`: Endpoints for managing long-term and episodic memories.
  - `/voice`: Bidirectional WebSocket audio streaming and avatar state machine.

### 3.2 Agent & Reasoning Engine (`core/agent/`)
- **NyxAgent**: Manages the multi-turn `Thought -> Tool -> Observation -> Response` cycle up to `MAX_ITERATIONS`.
- **ToolRegistry**: Registers definitions for LLM tool selection and dispatches execution through the safety filter.
- **Tools Supported**:
  - System tools: `get_battery_status`, `get_cpu_usage`, `get_ram_usage`, `get_current_time`.
  - Application tools: `open_application`, `focus_application`.
  - Planning tools: `create_plan`, `update_plan`, `complete_plan`.
  - Task & File tools: `create_task`, `list_tasks`, `read_file`, `organize_folder`.

### 3.3 Safety Architecture (`safety/`)
Every tool execution passes through strict multi-tier verification:
1. **Level 1: Safe** — Auto-executed (e.g. battery, time, system stats).
2. **Level 2: Confirmation** — Intercepted and requires user consent (e.g. open application, modify files).
3. **Level 3: High Risk** — Requires explicit password/validation.
4. **Level 4: Blocked** — Forbidden (e.g. arbitrary raw shell execution, `rm -rf`).
- **CommandValidator**: Enforces argument validation, regex sanitization, and path traversal prevention.

### 3.4 Multi-Layered Memory (`core/memory/`)
1. **Short-Term Memory**: Conversation history maintained in memory per conversation ID.
2. **Long-Term Memory**: Key-value user preferences, goals, and facts persisted in SQLite.
3. **Episodic Memory**: Journal entries of past milestones and events with timestamps.

### 3.5 Voice Pipeline (`voice/`)
- **Microphone**: Captured at 16,000 Hz mono PCM using `sounddevice`.
- **STT (Speech-to-Text)**: Local `faster-whisper` (`small` model default) with auto-language detection (English, Hindi, Marathi).
- **TTS (Text-to-Speech)**: Dual engine routing:
  - English: Kokoro TTS for high-fidelity natural speech.
  - Hindi & Marathi: pyttsx3 multilingual fallback.

### 3.6 Desktop & Hyprland Integration (`apps/desktop/`, `deployment/systemd/`)
- **Systemd User Units**:
  - `nyxai-core.service`: Backend service with automatic restart on failure.
  - `nyxai-ui.service`: Companion UI server.
  - `nyxai-voice.service`: Desktop daemon for IPC and global hotkeys.
- **Hyprland Shortcuts**:
  - `SUPER, J`: Dispatches window focus or launches browser app mode.
  - `SUPER, SPACE`: Triggers audio recording and voice interaction.
