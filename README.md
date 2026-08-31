# NyxAI 🌙

> Local-first AI companion and intelligent desktop agent for Linux.

NyxAI is a privacy-focused, fully local AI system built for Linux (Arch/EndeavourOS + Hyprland).
It combines conversational AI, voice interaction, desktop automation, and long-term memory —
running entirely on your hardware with no cloud dependency.

---

## Current Status — Phase 1: Backend Foundation ✅

The backend foundation is complete and working. Phase 1 delivers:

- **FastAPI backend** with `/health` and `/chat` endpoints
- **Local LLM** via Ollama (default: `qwen2.5:3b`, fully configurable)
- **Multilingual support** — English, Hindi, Marathi, Hinglish
- **LLM provider abstraction** — swap backends with zero code changes
- **NyxAI personality** via system prompt
- **Structured logging** with structlog
- **Configuration management** via Pydantic Settings + `.env`
- **23 automated tests** (run without GPU/Ollama)

---

## Hardware Target

| Component | Spec |
|-----------|------|
| CPU | Intel Core i7-14700HX |
| GPU | NVIDIA RTX 4050 Laptop (6 GB VRAM) |
| RAM | 16 GB |
| OS | EndeavourOS / Arch Linux |
| WM | Hyprland (Wayland) |

---

## Recommended Model

**`qwen2.5:3b`** — ~2 GB VRAM, excellent multilingual support (EN/HI/MR), strong instruction following.

```bash
ollama pull qwen2.5:3b
```

Change model without code changes:
```bash
OLLAMA_MODEL=llama3.2:3b make dev
```

---

## Quick Start

### Prerequisites
- [Ollama](https://ollama.ai) installed and running
- Python 3.11+

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/NyxAI.git
cd NyxAI

# Create virtual environment and install dependencies
make setup

# Pull the recommended model (one-time, ~2 GB)
make pull-model

# Copy environment config
cp .env.example .env

# Start the backend
make dev
```

### Test

```bash
# Health check
curl http://127.0.0.1:8000/health

# Chat in English
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello NyxAI!"}'

# Chat in Hinglish
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hey Nyx! आज काय plan आहे?"}'

# Interactive API docs
open http://127.0.0.1:8000/docs
```

### Run Tests

```bash
make test
# 23 passed — no GPU or Ollama required
```

---

## Architecture

```
User (curl / Tauri frontend)
        │
        ▼
  FastAPI Backend (:8000)
  ┌──────────────────────────┐
  │  GET  /health            │
  │  POST /chat              │
  │                          │
  │  ChatService             │
  │      │                   │
  │      ▼                   │
  │  LLMProvider (abstract)  │
  │      │                   │
  │      ▼                   │
  │  OllamaProvider          │
  └──────────┬───────────────┘
             │ HTTP REST
             ▼
       Ollama (:11434)
             │
             ▼
       qwen2.5:3b (local GPU)
```

---

## Project Structure

```
NyxAI/
├── api/                    # FastAPI backend (Phase 1)
│   └── app/
│       ├── main.py         # App entry point + lifespan
│       ├── config.py       # Pydantic Settings
│       ├── routers/        # HTTP endpoints
│       ├── services/       # Business logic
│       └── schemas/        # Request/response models
│
├── core/                   # Shared AI logic
│   └── brain/
│       ├── llm.py          # Abstract LLMProvider interface
│       ├── prompts.py      # NyxAI personality
│       └── providers/
│           └── ollama.py   # Ollama implementation
│
├── tools/                  # Agent tools (Phase 2)
├── safety/                 # Permission system (Phase 2)
├── voice/                  # STT/TTS pipeline (Phase 3)
├── apps/companion/         # React/Tauri UI (Phase 4)
├── training/               # LoRA fine-tuning (Phase 7)
└── deployment/systemd/     # systemd services (Phase 8)
```

---

## Development Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Backend Foundation | ✅ Complete | FastAPI, Ollama, chat API, logging, tests |
| 2 — Agent & Tools | 🔜 Next | Tool registry, open_app, battery, browser |
| 3 — Voice | ⏳ Planned | Push-to-talk, STT (faster-whisper), TTS |
| 4 — Companion UI | ⏳ Planned | React + Tauri, animated avatar, SUPER+J |
| 5 — Memory | ⏳ Planned | Short/long-term, episodic, SQLite, vectors |
| 6 — Advanced Agent | ⏳ Planned | Multi-step planning, file tools |
| 7 — Fine-Tuning | ⏳ Planned | LoRA/QLoRA for Hindi/tool-calling |
| 8 — Deployment | ⏳ Planned | systemd services, auto-start |

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```env
OLLAMA_MODEL=qwen2.5:3b       # Model to use
OLLAMA_BASE_URL=http://localhost:11434
LOG_LEVEL=INFO
HOST=127.0.0.1
PORT=8000
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| LLM Runtime | Ollama |
| HTTP Client | httpx (async) |
| Logging | structlog |
| Testing | pytest, pytest-asyncio |
| Frontend (future) | React, TypeScript, Vite, Tauri |
| Database (future) | SQLite → PostgreSQL |
| Voice (future) | faster-whisper, Kokoro TTS |

---

## License

MIT
