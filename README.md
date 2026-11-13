# NyxAI

Local-first AI companion, voice assistant, and desktop agent for Linux powered by [Ollama](https://ollama.ai).

---

## Prerequisites

- **Linux** (Arch / EndeavourOS, Debian / Ubuntu, or Fedora)
- **Python** 3.11+
- **Node.js & npm** (for the Companion UI)
- **[Ollama](https://ollama.com/download)** (installed automatically on Arch via `install.sh`, or install manually on other distros)

---

## Installation

### One-Command Setup (Recommended)

```bash
git clone https://github.com/nyxus-git/NyxAI.git
cd NyxAI
./scripts/install.sh
```

`install.sh` sets up system dependencies, creates `.venv`, creates `.env`, pulls `qwen2.5:3b` via Ollama, builds the Companion UI, installs the `nyxai` launcher (`~/.local/bin/nyxai`) and desktop menu entry, and configures `systemd` user units.

Useful installer flags:

```bash
./scripts/install.sh -y                  # Non-interactive install with defaults
./scripts/install.sh --model=llama3.2:3b # Use a different Ollama model
./scripts/install.sh --skip-model        # Skip pulling the Ollama model
./scripts/install.sh --enable-service    # Enable nyxai-core service at login
```

### Manual / Minimal Setup (Backend & CLI only)

```bash
git clone https://github.com/nyxus-git/NyxAI.git
cd NyxAI

cp .env.example .env
make setup
make pull-model
```

---

## User Guide

### Launch the Desktop App

If you ran `./scripts/install.sh`, open **NyxAI** from your Application Menu or run:

```bash
nyxai
```

Or launch directly from the repo:

```bash
make app
```

Inside the app's top bar, you can switch between the stylized companion, upload a portrait photo (**Upload Girl Photo**), or load a 3D `.vrm`/`.glb` character.

---

### Run in Development Mode

Start both the backend API (`http://127.0.0.1:8000`) and Companion Web UI (`http://127.0.0.1:5173`) together:

```bash
./scripts/run.sh dev
```

Or run them separately:

```bash
make dev   # FastAPI backend (API docs at http://127.0.0.1:8000/docs)
make ui    # Companion Web UI dev server
```

---

### Voice Chat (Push-to-Talk CLI)

Ensure Ollama and the backend (`make dev`) are running, then start voice chat:

```bash
make voice             # Agent mode (with desktop/system tools)
make voice-companion   # Companion mode (chat only)
```

Press **Enter** to start recording, press **Enter** again to stop and send, and press **Ctrl+C** to exit.

Optional CLI flags (for CPU-only systems, custom Whisper size, or disabling TTS):

```bash
.venv/bin/python scripts/voice_chat.py --mode agent --device cpu --no-tts
```

| Flag | Options | Description |
|------|---------|-------------|
| `--mode` | `agent`, `companion` | Enable tools (`agent`) or chat only (`companion`) |
| `--whisper` | `tiny`, `base`, `small`, `medium` | Whisper STT model size (default: `small`) |
| `--device` | `cuda`, `cpu` | Whisper inference device (default: `cuda`) |
| `--language` | `auto`, `en`, `hi`, `mr` | Speech recognition language (default: `auto`) |
| `--no-tts` | — | Disable spoken audio output |

---

### API Usage

Check server health:

```bash
curl http://127.0.0.1:8000/health
```

Send a chat message:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello NyxAI!"}'
```

---

### Background Services & Desktop Shortcuts

Manage NyxAI background `systemd` user services:

```bash
nyxai start    # or: make service-start
nyxai status   # or: make service-status
nyxai logs     # or: make service-logs
nyxai stop     # or: make service-stop
```

Optional global shortcut to toggle the app window (ensure `~/.local/bin` is in your `PATH`):

- **KDE Plasma / GNOME:** Bind a custom shortcut to `~/.local/bin/nyxai toggle`
- **Hyprland** (`~/.config/hypr/hyprland.conf`):
  ```ini
  bind = SUPER, J, exec, ~/.local/bin/nyxai toggle
  bind = SUPER, SPACE, exec, ~/.local/bin/nyxai ptt
  ```

---

## Configuration

Key settings in `.env`:

```env
HOST=127.0.0.1
PORT=8000

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

DEFAULT_LANGUAGE=auto   # auto, en, hi, mr

WHISPER_MODEL=small
WHISPER_DEVICE=cuda     # set to cpu if no NVIDIA GPU
TTS_ENGINE=kokoro
```

Override the model for a single dev run:

```bash
OLLAMA_MODEL=llama3.2:3b make dev
```

---

## Running Tests

```bash
make test
```

---

## Documentation

- [Tools, Technologies & Frameworks Guide](docs/TOOLS_AND_TECHNOLOGIES.md) — Comprehensive breakdown of all tools, libraries, models, and frameworks used in NyxAI and why they were chosen.
- [Next-Level Implementation Plan (NyxAI 2.0)](docs/NEXT_LEVEL_IMPLEMENTATION_PLAN.md) — Architectural roadmap for multi-agent swarm, "Hey Nyx" wake word, communications hub, and JARVIS HUD.
- [Architecture & Technical Design](docs/ARCHITECTURE.md) — Subsystem architecture and service lifecycles.
- [API Reference](docs/API.md) — REST, WebSocket, and Desktop IPC specifications.

---

## License

MIT
