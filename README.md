# NyxAI 🌙

> Local-first AI companion and intelligent desktop agent for Linux.

NyxAI is a privacy-focused, fully local AI system built for Linux (Arch/EndeavourOS + Hyprland).
It combines conversational AI, voice interaction, desktop automation, and long-term memory —
running entirely on your hardware with no cloud dependency.

---

## What NyxAI Can Do

- 🗣️ **Multilingual voice chat** — English, Hindi, Marathi, Hinglish — speak naturally, get a spoken response
- 🤖 **Desktop agent** — open apps, search the web, manage files, check system stats, set task reminders
- 🧠 **4-layer memory** — remembers facts about you across all sessions (short-term, long-term, episodic, semantic)
- 🔒 **Privacy-first** — everything runs locally, nothing leaves your machine
- ⚡ **Push-to-talk** — `Super+Space` to speak, `Super+J` to toggle the companion UI
- 🎛️ **Fine-tunable** — LoRA/QLoRA training pipeline included for personalizing the model

---

## Hardware

| Component | Spec |
|-----------|------|
| CPU | Intel Core i7-14700HX |
| GPU | NVIDIA RTX 4050 Laptop (6 GB VRAM) |
| RAM | 16 GB |
| OS | EndeavourOS / Arch Linux |
| WM | Hyprland (Wayland) |

---

## Recommended Model

**`qwen2.5:3b`** — ~2 GB VRAM, excellent multilingual support (EN/HI/MR), native function calling.

```bash
ollama pull qwen2.5:3b
```

Swap the model without touching any code:
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
git clone https://github.com/nyxus-git/NyxAI.git
cd NyxAI

# Create virtualenv and install all dependencies
make setup

# Pull the default model (one-time, ~2 GB)
make pull-model

# Copy config
cp .env.example .env

# Start the backend
make dev
```

### Test It

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
xdg-open http://127.0.0.1:8000/docs
```

### Run Tests

```bash
make test
# All tests pass — no GPU or Ollama required
```

---

## Architecture

```
User (Voice / UI / curl)
        │
        ▼
  FastAPI Backend (:8000)
  ┌─────────────────────────────────────────┐
  │  /health  /chat  /agent  /voice  /memory│
  │                                         │
  │  NyxAgent ←──── ToolRegistry            │
  │      │               │                  │
  │      │          [battery, browser,       │
  │      │           files, tasks,           │
  │      │           planning, system]       │
  │      │                                  │
  │  MemoryService                          │
  │      ├── ShortTermMemory  (SQLite)       │
  │      ├── LongTermMemory   (SQLite)       │
  │      ├── EpisodicMemory   (SQLite)       │
  │      └── SemanticMemory   (ChromaDB)     │
  │                                         │
  │  LLMProvider (abstract)                 │
  │      └── OllamaProvider                 │
  └──────────────┬──────────────────────────┘
                 │ HTTP REST
                 ▼
           Ollama (:11434)
                 │
                 ▼
           qwen2.5:3b  (RTX 4050, local GPU)

Voice Pipeline (separate service):
  Mic → faster-whisper (CUDA) → text → NyxAgent → Kokoro TTS / pyttsx3 → Speaker
```

---

## Project Structure

```
NyxAI/
├── api/                    # FastAPI backend
│   └── app/
│       ├── main.py         # App entry point + lifespan
│       ├── config.py       # Pydantic Settings
│       ├── routers/        # HTTP endpoints
│       ├── services/       # Business logic
│       └── schemas/        # Request/response models
│
├── core/                   # Shared AI logic
│   ├── brain/
│   │   ├── llm.py          # Abstract LLMProvider interface
│   │   ├── prompts.py      # NyxAI personality & system prompt
│   │   ├── language.py     # Unicode-based language detection
│   │   └── providers/
│   │       └── ollama.py   # Ollama implementation
│   ├── agent/
│   │   ├── agent.py        # Agentic reasoning loop
│   │   ├── tool_registry.py
│   │   └── schemas.py
│   └── memory/
│       ├── short_term.py   # SQLite conversation history
│       ├── long_term.py    # Persistent user facts
│       ├── episodic.py     # Event journal
│       └── semantic.py     # ChromaDB vector search
│
├── tools/                  # Agent tools
│   ├── system/             # Battery, CPU, RAM, time
│   ├── browser/            # Web search, open URL, read page
│   ├── files/              # Read, list, search, move, copy, delete
│   ├── tasks/              # Add, list, complete tasks, reminders
│   └── planning/           # Multi-step plan creation
│
├── safety/                 # Permission system & command validator
├── voice/                  # STT (faster-whisper) + TTS (Kokoro/pyttsx3)
├── apps/companion/         # React + Vite + Tauri companion UI
├── training/               # LoRA/QLoRA fine-tuning pipeline
└── deployment/systemd/     # systemd user services
```

---

## Persistent Deployment & Desktop Integration

NyxAI runs as systemd user services — no root required, auto-starts on login.

### Install
```bash
make service-install
```

### Service Management
```bash
make service-start    # Start all NyxAI services
make service-status   # Check unit states and backend health
make service-logs     # Stream journalctl logs
make service-stop     # Stop all services
```

### Hyprland Keybindings
Add to `~/.config/hypr/hyprland.conf`:
```ini
bind = SUPER, J, exec, ~/Projects/NyxAI/scripts/run.sh toggle
bind = SUPER, SPACE, exec, ~/Projects/NyxAI/scripts/run.sh ptt
```

### Voice Mode
```bash
make voice            # Push-to-talk agent mode
make voice-companion  # Push-to-talk companion mode
```

---

## Fine-Tuning

NyxAI includes a QLoRA training pipeline to fine-tune `qwen2.5:3b` on custom datasets.
Designed to run within 6 GB VRAM using 4-bit quantization + gradient checkpointing.

```bash
python training/scripts/train_lora.py \
  --model_id Qwen/Qwen2.5-3B-Instruct \
  --data_path training/datasets/processed/train.jsonl
```

---

## Configuration

Copy `.env.example` to `.env`:

```env
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434
LOG_LEVEL=INFO
HOST=127.0.0.1
PORT=8000
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| LLM Runtime | Ollama (`qwen2.5:3b`) |
| HTTP Client | httpx (async) |
| Validation | Pydantic v2 |
| Logging | structlog |
| STT | faster-whisper (CTranslate2, CUDA) |
| TTS | Kokoro ONNX (EN), pyttsx3/eSpeak (HI/MR) |
| Memory | aiosqlite + ChromaDB |
| Fine-Tuning | HuggingFace PEFT, TRL, bitsandbytes |
| Frontend | React, TypeScript, Vite, Tauri |
| Testing | pytest, pytest-asyncio |
| Deployment | systemd user services |

---

## License

MIT
