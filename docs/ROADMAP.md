# NyxAI — Development Roadmap

This document tracks the phased development of NyxAI as outlined in [docs/PRD.md](file:///home/nyyxus-preditor/Projects/NyxAI/docs/PRD.md).

---

## Phases Overview

| Phase | Title | Status | Description | Key Deliverables |
|-------|-------|--------|-------------|------------------|
| **1** | **Backend Foundation** | ✅ Complete | Core FastAPI server, config management, logging, and abstract LLM provider. | `/health`, `/chat`, OllamaProvider, Pydantic settings. |
| **2** | **Agent & Tools** | ✅ Complete | Structured tool calling, tool registry, safety validation, system inspection tools. | ToolRegistry, CommandValidator, get_battery_status, open_application. |
| **3** | **Voice Pipeline** | ✅ Complete | Speech-to-Text and Text-to-Speech audio processing with multilingual support. | faster-whisper STT, Kokoro / pyttsx3 TTS, WebSocket `/voice`. |
| **4** | **Companion UI** | ✅ Complete | Animated interactive avatar frontend connected via WebSocket state machine. | React + Vite UI (`apps/companion`), avatar state sync (idle/thinking/speaking). |
| **5** | **Memory System** | ✅ Complete | Multi-layered memory (short-term, long-term, episodic) backed by SQLite database. | MemoryDatabase (`data/nyx_memory.db`), MemoryService, `/memory/*` endpoints. |
| **6** | **Advanced Agent** | ✅ Complete | Multi-step task planning, task reminders, file reading, searching, and organization. | Task tools, File tools, Planning tools (`create_plan`, `update_plan`). |
| **7** | **Fine-Tuning Setup** | ✅ Complete | LoRA/QLoRA dataset preparation, validation, training pipeline, and evaluation harness. | `training/scripts/` (dataset_builder, train_lora, export_model, evaluate). |
| **8** | **Persistent Deployment** | ✅ Complete | Systemd user units, auto-start upon login, recovery, and Hyprland desktop integration. | `deployment/systemd/` (*.service), `scripts/install.sh`, `scripts/run.sh`, `apps/desktop/main.py`. |

---

## Detailed Milestone Status

### Phase 1: Foundation
- [x] FastAPI application structure with lifespan management
- [x] `GET /health` with LLM connectivity verification
- [x] `POST /chat` with streaming and non-streaming responses
- [x] Abstract `LLMProvider` interface
- [x] `OllamaProvider` with `qwen2.5:3b` default
- [x] Structured JSON logging via `structlog`

### Phase 2: Agent Tools
- [x] `ToolRegistry` with type-safe parameter schemas
- [x] `CommandValidator` preventing command injection and directory traversal
- [x] Multi-tier safety policy (SAFE, CONFIRMATION, HIGH_RISK, BLOCKED)
- [x] System inspection tools (battery, CPU, RAM, current time)
- [x] Application launcher tools

### Phase 3: Voice System
- [x] `PushToTalkListener` using sounddevice (16kHz mono audio)
- [x] Local `WhisperTranscriber` (faster-whisper) with Hindi, Marathi, English auto-detection
- [x] Dual-engine TTS speaker (`Kokoro` for English, `pyttsx3` for Hindi/Marathi)
- [x] `GET /voice` bidirectional WebSocket upgrade

### Phase 4: Companion UI
- [x] Vite + React companion interface in `apps/companion`
- [x] Real-time avatar state transitions (`idle`, `thinking`, `speaking`)
- [x] Chat history and voice waveforms in UI

### Phase 5: Memory System
- [x] Async SQLite database schema (`data/nyx_memory.db`)
- [x] Short-term conversation context storage and pruning
- [x] Long-term user facts and preference storage
- [x] Episodic memory logging significant interactions
- [x] REST endpoints for managing and inspecting memories

### Phase 6: Advanced Agent
- [x] Multi-step plan tracking (`create_plan`, `update_plan`, `complete_plan`)
- [x] Task scheduling and automated reminder poller
- [x] File discovery, content reading, and safe folder organization

### Phase 7: Fine-Tuning Pipeline
- [x] Dataset conversion utility to JSONL conversational format
- [x] HuggingFace dataset validator
- [x] PEFT / LoRA / QLoRA training script (`training/scripts/train_lora.py`)
- [x] GGUF / Ollama model export script
- [x] Benchmark evaluation script

### Phase 8: Persistent Deployment & Desktop Integration
- [x] Systemd user service `nyxai-core.service`
- [x] Systemd user service `nyxai-ui.service`
- [x] Systemd user service `nyxai-voice.service`
- [x] Automated one-click installer (`scripts/install.sh`)
- [x] Unified lifecycle runner (`scripts/run.sh`)
- [x] Hyprland / Wayland hotkey integration:
  - `SUPER + J` -> Toggle Companion UI
  - `SUPER + SPACE` -> Push-To-Talk voice trigger
- [x] Desktop integration controller (`apps/desktop/main.py`)
