# NyxAI — Tools, Technologies & Frameworks Guide

> A comprehensive technical reference explaining every tool, library, technology, and framework powering **NyxAI**, detailing **why** each was chosen and **how** it advances the project's mission as a 100% local, privacy-first AI companion and desktop agent.

---

## 1. System Philosophy & Architecture Overview

NyxAI is designed from first principles around three non-negotiable architectural requirements:
1. **Zero Cloud Dependency & Absolute Privacy**: All reasoning, speech-to-text, text-to-speech, memory storage, and avatar animation run entirely on local consumer hardware without telemetry or external API calls.
2. **Resource Efficiency on Linux**: Must operate smoothly on mainstream hardware (e.g., 16 GB RAM, 6 GB VRAM NVIDIA RTX 4050 Laptop GPU, or CPU fallback) across any Linux distribution (Arch, EndeavourOS, Debian/Ubuntu, Fedora) and desktop environments (KDE Plasma, GNOME, XFCE, Hyprland).
3. **Decoupled, Modular Subsystems**: The cognitive brain, voice pipeline, desktop window shell, web UI, safety layer, and memory services operate as discrete, testable components communicating over standard protocols (HTTP REST, WebSockets, Unix domain sockets).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DESKTOP & WINDOW SHELL LAYER                         │
│  PyQt6 + Qt6 WebEngine  │  Linux XDG Desktop  │  Hyprland IPC (hyprctl)    │
│  Single-Instance Unix Domain Socket  │  System Tray Icon (QSystemTrayIcon)  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    INTERACTIVE COMPANION UI (FRONTEND)                     │
│  React 18  │  TypeScript  │  Vite  │  Tailwind/CSS  │  Lucide-React          │
│  Three.js & @pixiv/three-vrm (3D Avatar)  │  MediaPipe Tasks-Vision (Photo) │
│  Web Audio API (FFT Lip-Sync & Visemes)   │  WebSockets (Audio/State Feed)  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / WebSockets
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                      BACKEND & ORCHESTRATION LAYER                         │
│  Python 3.11+ Asyncio  │  FastAPI (REST + WS)  │  Uvicorn ASGI              │
│  Pydantic v2 & Pydantic-Settings  │  Structlog Structured Logging           │
└──────────────────┬───────────────────┬───────────────────┬──────────────────┘
                   │                   │                   │
┌──────────────────▼──────┐ ┌──────────▼─────────┐ ┌───────▼──────────────────┐
│    COGNITIVE BRAIN      │ │   VOICE PIPELINE   │ │     MEMORY SYSTEM        │
│ Ollama (qwen2.5:3b)     │ │ faster-whisper STT │ │ aiosqlite (Short/Long/Ep)│
│ Unicode Language Router │ │ kokoro-onnx TTS    │ │ ChromaDB (Semantic Vec)  │
│ NyxAgent ReAct Loop     │ │ pyttsx3 / eSpeak   │ │ Ollama nomic-embed-text  │
│ ToolRegistry & Schemas  │ │ sounddevice / ALSA │ │ Sliding Window Truncation│
└──────────────────┬──────┘ └────────────────────┘ └──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────────────────────┐
│                   SAFETY GUARDRAILS & BUILT-IN TOOLS                        │
│  CommandValidator (Regex/Traversal)  │  Multi-Tier Permission Policy        │
│  System (psutil)  │  Web (httpx + bs4)  │  Files (pathlib)  │  Tasks (sqlite)│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Master Technology Stack Matrix

| Domain / Layer | Technology / Tool | Version / Spec | Primary Role | Why We Chose It |
|---|---|---|---|---|
| **Language Runtime** | **Python** | `3.11+` | Backend, agent logic, ML inference, system scripting | Rich AI/ML ecosystem, modern `asyncio` optimizations, and native OS bindings. |
| **Backend API** | **FastAPI** | `>=0.115.0` | Asynchronous REST and WebSocket web server | Native async, high throughput, automatic OpenAPI documentation, clean dependency injection. |
| **ASGI Server** | **Uvicorn** | `>=0.30.0` | High-performance ASGI application server | Built on `uvloop` and `httptools` for lightning-fast asynchronous HTTP and WebSocket event handling. |
| **Data Validation** | **Pydantic v2** | `>=2.7.0` | Schema validation and serialization | Rust-backed performance (`pydantic-core`), strict typing, and seamless OpenAPI integration. |
| **Configuration** | **Pydantic-Settings** | `>=2.3.0` | Type-safe environment management | Automatically loads `.env` variables into validated Python configurations with zero boilerplate. |
| **Structured Logging** | **Structlog** | `>=24.2.0` | Contextual structured logging | Produces auditable JSON/key-value logs with bound request contexts for painless debugging. |
| **Desktop Shell** | **PyQt6** & **PyQt6-WebEngine** | `>=6.7.0` | Native Linux desktop application window | Embeds Chromium WebGL/WebAudio without Electron memory bloat; provides native system tray and window framing. |
| **Single-Instance IPC**| **Unix Domain Sockets** | POSIX standard | Single-instance lock and instant toggle messaging | Guarantees only one app instance runs; routes hotkeys (`SUPER+J`) directly to the running window. |
| **LLM Inference Host** | **Ollama** | Local daemon (`:11434`)| Local Large Language Model runner | Supports GGUF models with GPU acceleration (CUDA), zero setup overhead, and native function/tool calling. |
| **Primary LLM** | **`qwen2.5:3b`** | 3 Billion Parameters | Conversational reasoning, planning, tool selection | Exceptional multilingual fluency (EN, HI, MR), low VRAM footprint (~2-3 GB), and reliable tool-calling JSON tokens. |
| **Language Detection** | **Unicode Range Classifier** | Custom pure Python | Pre-TTS script and dialect routing | Zero latency, zero external dependencies; uses character codepoints to route text to the proper speech engine. |
| **Speech-to-Text** | **faster-whisper** | `>=1.1.0` | Fast speech recognition (English, Hindi, Marathi) | CTranslate2-accelerated Whisper; up to 4x faster and uses less VRAM with FP16/INT8 CUDA execution. |
| **Audio I/O** | **sounddevice** & **soundfile** | `>=0.5.0` / `>=0.12.0` | Real-time microphone capture and audio playback | Direct low-latency integration with Linux PipeWire, PulseAudio, and ALSA audio backends. |
| **English TTS** | **kokoro-onnx** | `>=0.4.0` | High-fidelity neural voice synthesis | 82M parameter natural voice running on ONNX CPU; provides broadcast-quality English audio without touching GPU VRAM. |
| **Indic TTS** | **pyttsx3** + **eSpeak-NG** | `>=2.90` | Multilingual offline speech synthesis | Lightweight, reliable speech synthesis for Hindi and Marathi phonemes without heavy deep learning overhead. |
| **Relational Storage** | **aiosqlite** | `>=0.20.0` | Async SQLite database driver | Non-blocking database access for conversation histories, long-term user facts, and task reminders. |
| **Vector Database** | **ChromaDB** | `>=0.5.0` | Local semantic memory vector store | Fully embedded vector database with persistent storage on disk for similarity-based knowledge retrieval. |
| **Embeddings** | **Ollama `nomic-embed-text`** | 768 dimensions | Semantic vector embeddings generation | State-of-the-art local text embeddings for indexing and searching long-term user memories. |
| **Frontend Framework** | **React 18** | `^18.3.1` | Declarative user interface | Efficient component lifecycle, reactive hooks, and rich ecosystem for the companion interface. |
| **Frontend Typing** | **TypeScript** | `^5.4.5` | Type safety across UI and API client | Eliminates runtime bugs, guarantees typed WebSocket payloads, and improves maintainability. |
| **Build & Dev Tool** | **Vite** | `^5.2.11` | Modern frontend bundler and dev server | Instant hot module replacement (HMR) and optimized Rollup-based production builds. |
| **3D Avatar Engine** | **Three.js** & **@pixiv/three-vrm** | `^0.187.0` / `^3.5.5` | 3D rendering and VRM humanoid animation | Industry-standard WebGL rendering with spring-bone hair physics, gaze tracking, and facial blend shapes. |
| **Face Landmark Vision**| **@mediapipe/tasks-vision** | `^1.2.2` | 478 3D facial landmark detection | Runs locally via WebAssembly to track facial contours on user-uploaded 2D photos for real-time lip sync and blinking. |
| **Audio Lip Sync** | **Web Audio API** | Browser Native | FFT frequency analysis and viseme generation | Extracts real-time audio volume and frequency bins to map mouth shapes (`closed`, `slight`, `open`, `wide`). |
| **System Metrics Tool**| **psutil** | `>=6.0.0` | Hardware and process monitoring | Provides accurate CPU, RAM, battery, thermal, and sensor data for agent introspection tools. |
| **Web Scraping Tool** | **httpx** & **BeautifulSoup4** | `>=0.27.0` / `>=4.12.3`| Async HTTP requests and HTML parsing | Powers web search result fetching and readable text extraction from online articles. |
| **Fine-Tuning Stack** | **PEFT**, **TRL**, **bitsandbytes**| `>=0.11`, `>=0.9`, `>=0.43`| QLoRA instruction tuning | Enables fine-tuning 3B LLMs on consumer 6 GB VRAM GPUs using 4-bit NormalFloat quantization. |
| **Service Supervisor** | **systemd (User Units)** | Linux standard | Persistent background daemon lifecycle | Starts NyxAI automatically on user login, manages dependencies, restarts on failure, and captures journal logs. |

---

## 3. Backend & Core Architecture

### Python 3.11+ & Asyncio
- **Why We Use It**: Python is the lingua franca of AI, machine learning, and Linux system engineering. Python 3.11+ introduced major runtime optimizations (Specializing Adaptive Interpreter), delivering 10-60% faster execution than Python 3.10. Furthermore, native `asyncio` allows non-blocking concurrency across HTTP endpoints, database queries, and WebSocket channels.
- **How It Helps the Project**: NyxAI coordinates multiple asynchronous tasks simultaneously — streaming microphone input, running background reminder schedulers, handling WebSocket frames, and executing asynchronous database queries — without blocking the main event loop or requiring complex multi-process synchronization.

### FastAPI & Uvicorn
- **Why We Use It**: FastAPI provides industry-leading performance comparable to NodeJS and Go, built on Starlette and Pydantic. It provides automated OpenAPI/Swagger interactive documentation (`/docs`), robust dependency injection, and native support for both REST and bidirectional WebSockets.
- **How It Helps the Project**:
  - Serves REST endpoints (`/chat`, `/health`, `/memory`, `/avatar`) and WebSocket channels (`/voice/ws`) from a single unified application.
  - Automatically validates incoming JSON payloads and outputs clear 422 validation errors if fields are missing or malformed.
  - Generates live API documentation allowing developers to inspect and test agent capabilities via their browser.
  - Uvicorn delivers ASGI asynchronous performance with minimal memory overhead, hosting the service reliably at `127.0.0.1:8000`.

### Pydantic v2 & Pydantic-Settings
- **Why We Use It**: Pydantic v2 was rewritten in Rust (`pydantic-core`), making data validation and JSON serialization 5x to 50x faster than v1. `pydantic-settings` provides a disciplined way to manage application configuration.
- **How It Helps the Project**:
  - `api/app/config.py` inherits from `BaseSettings` to parse and validate `.env` configuration (e.g., `OLLAMA_MODEL`, `HOST`, `PORT`, `TTS_ENGINE`, `WHISPER_DEVICE`) with type enforcement and default values.
  - Structured schemas in `core/agent/schemas.py` (`ToolCall`, `ToolResult`, `AgentStep`) enforce strict contracts between the LLM output parser and the tool execution engine.

### Structlog
- **Why We Use It**: Traditional standard-library Python logging produces unstructured text strings that are difficult to search, parse, and analyze programmatically. Structlog builds structured event dictionaries that can render as human-readable colorized terminal output during development and structured JSON in production logs.
- **How It Helps the Project**:
  - Captures contextual metadata on every event: e.g., `logger.info("tool_dispatched", tool="get_battery_status", execution_time_ms=12.4, status="success")`.
  - Enables effortless troubleshooting when streaming systemd user journal logs via `make service-logs` or `nyxai logs`.

---

## 4. AI Brain & Large Language Model (LLM) Inference

### Ollama (`http://localhost:11434`)
- **Why We Use It**: Ollama is a lightweight, open-source execution runtime for quantized LLMs (GGUF format via `llama.cpp`). It automatically detects and leverages NVIDIA CUDA, AMD ROCm, or CPU AVX/AVX2 instruction sets, managing model memory paging and concurrency transparently.
- **How It Helps the Project**:
  - Eliminates external API keys, rate limits, credit cards, and cloud privacy liabilities.
  - Exposes an async REST API that NyxAI queries using `httpx`.
  - Provides native tool/function calling support: when tools are supplied in the request payload, Ollama prompts the model using internal grammar constraints to emit clean, syntactically valid JSON tool calls.

### Qwen2.5-3B-Instruct (Default Brain)
- **Why We Use It**:
  - **VRAM Budget**: Consumes only ~2.2 GB VRAM in 4-bit/8-bit quantization. On a modern 6 GB laptop GPU (like an RTX 4050), this leaves ~3.8 GB VRAM completely free for the `faster-whisper` STT model, WebGL graphics, and OS compositor buffers.
  - **Multilingual Excellence**: Trained on massive multilingual datasets with exceptional support for English, Hindi (हिन्दी), Marathi (मराठी), and code-switched Hinglish.
  - **Tool Calling Precision**: Demonstrates high instruction-following adherence and low hallucination rates when formatting tool parameters compared to other models in the 1B–3B class.
- **How It Helps the Project**: Acts as the conversational companion and agentic brain. It can converse playfully, switch naturally between languages, plan multi-step operations, and trigger desktop tools.

### Dynamic Unicode Language Detector (`core/brain/language.py`)
- **Why We Use It**: Heavy NLP language identification libraries (such as `langdetect` or `fasttext`) introduce multi-megabyte dependencies, disk I/O, and CPU latency. Because NyxAI primarily needs to decide whether text should be spoken using English neural TTS or Indic phonemic TTS, linguistic script detection is sufficient.
- **How It Helps the Project**:
  - Inspects Unicode code point ranges (`0x0900` to `0x097F` for Devanagari).
  - Uses an in-memory set of Marathi-specific vocabulary markers (`आहे`, `नाही`, `आपण`, `कसे`, `काय`, `बघ`) to distinguish Marathi from Hindi.
  - Executes in less than 0.1 milliseconds with zero third-party dependencies, allowing instantaneous TTS routing.

---

## 5. Agentic Loop, Tools & Registry

### NyxAgent ReAct Loop (`core/agent/agent.py`)
- **Why We Use It**: A simple single-turn chatbot can only reply with what it knows. NyxAgent implements an iterative reasoning loop inspired by the **ReAct (Reasoning + Acting)** paradigm:
  $$\text{Thought} \longrightarrow \text{Action (Tool Call)} \longrightarrow \text{Observation (Tool Output)} \longrightarrow \text{Final Answer}$$
- **How It Helps the Project**:
  - When a user asks *"What is my battery level, and can I watch a movie?"*, NyxAgent does not guess: it queries `get_battery_status`, observes the percentage and discharge rate, and then synthesizes an informed answer.
  - Includes a hallucination retry mechanism: if the LLM attempts to invoke a non-existent tool or formats invalid arguments, the agent feeds the error message back to the LLM to self-correct within `MAX_ITERATIONS`.

### ToolRegistry (`core/agent/tool_registry.py`)
- **Why We Use It**: Decouples tool definitions from execution logic. Each tool provides a `ToolDefinition` (name, description, JSON schema parameters) and an executable Python handler (sync or async).
- **How It Helps the Project**:
  - Automatically translates internal tool definitions into Ollama's native tool calling format.
  - Intercepts all tool execution requests to verify safety policies and parameter validation before invoking the handler.

### Comprehensive Built-In Tool Suite

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    BUILT-IN AGENT TOOLS                     │
  ├──────────────────┬──────────────────────┬───────────────────┤
  │ Category         │ Tool Function        │ Technology Used   │
  ├──────────────────┼──────────────────────┼───────────────────┤
  │ System Metrics   │ get_battery_status   │ psutil            │
  │                  │ get_cpu_usage        │ psutil            │
  │                  │ get_ram_usage        │ psutil            │
  │                  │ get_system_info      │ platform, uname   │
  │                  │ get_current_time     │ datetime          │
  │                  │ get_gpu_status       │ nvidia-smi / NVML │
  ├──────────────────┼──────────────────────┼───────────────────┤
  │ Applications     │ open_application     │ subprocess, XDG   │
  ├──────────────────┼──────────────────────┼───────────────────┤
  │ Web & Browsing   │ web_search           │ httpx, bs4, DDG   │
  │                  │ read_webpage         │ httpx, bs4        │
  │                  │ open_url             │ webbrowser        │
  ├──────────────────┼──────────────────────┼───────────────────┤
  │ File Management  │ list_directory       │ os, pathlib       │
  │                  │ read_file            │ pathlib           │
  │                  │ search_files         │ os.walk           │
  │                  │ move_file            │ shutil            │
  │                  │ copy_file            │ shutil            │
  │                  │ delete_file          │ os.remove         │
  ├──────────────────┼──────────────────────┼───────────────────┤
  │ Task & Reminders │ add_task             │ aiosqlite         │
  │                  │ list_tasks           │ aiosqlite         │
  │                  │ complete_task        │ aiosqlite         │
  │                  │ set_reminder         │ aiosqlite, asyncio│
  ├──────────────────┼──────────────────────┼───────────────────┤
  │ Planning         │ create_plan          │ JSON state        │
  │                  │ update_plan          │ JSON state        │
  └──────────────────┴──────────────────────┴───────────────────┘
```

1. **`psutil` (System Tools)**: Reads cross-platform OS sensors, battery charge, CPU percentages across cores, virtual memory usage, and thermal states without shelling out to external command-line tools.
2. **`httpx` & `BeautifulSoup4` (Browser Tools)**: Performs lightweight web search via DuckDuckGo HTML endpoints and extracts clean readable text from web pages (stripping `<script>`, `<style>`, and navigation headers), enabling the agent to search the live web for up-to-date information.
3. **`pathlib` & `shutil` (File Management Tools)**: Provides robust file manipulation with sandboxed relative/absolute path normalization and directory traversal protection.
4. **`aiosqlite` (Task & Reminder Tools)**: Persists user to-dos, priorities, completion statuses, and ISO-8601 reminder timestamps with a background asynchronous poller that alerts the user when a reminder fires.
5. **Planning Tools**: Enables the agent to break down complex goals (e.g., *"Set up a new Python project with git and tests"*) into discrete steps, track progress, and report status.

---

## 6. Safety & Security Guardrails

### Permission Tiers (`safety/policy.py`)
NyxAI categorizes every tool call into one of four safety tiers:
1. **Level 1: SAFE (Auto-Executed)**: Read-only, zero side-effect operations (`get_battery_status`, `get_current_time`, `get_ram_usage`, `list_tasks`). Executed instantly without user interruption.
2. **Level 2: CONFIRMATION_REQUIRED (Interactive Consent)**: Operations that modify state, open apps, or touch the file system (`open_application`, `delete_file`, `move_file`). Held in pending status until the user approves or rejects them via the `/chat/confirm` API or desktop prompt.
3. **Level 3: ELEVATED (Privileged Operations)**: Sensitive commands requiring explicit validation.
4. **Level 4: BLOCKED (Forbidden)**: High-risk operations that are permanently rejected (`sudo`, disk wiping, fork bombs, raw shell access).

### `CommandValidator` (`safety/command_validator.py`)
- **Why We Use It**: LLMs can be vulnerable to prompt injection or hallucinate destructive arguments. Hardcoded programmatic validation ensures unsafe commands never reach the OS shell.
- **How It Helps the Project**:
  - **Directory Traversal Defense**: Rejects file paths containing `..` or attempts to escape sanctioned directories.
  - **Dangerous Command Blacklist**: Blocks shell patterns containing `rm -rf`, `mkfs`, `dd if=`, `:(){ :|:& };:`, `chmod -R 777 /`, and access to sensitive files (`/etc/shadow`, `~/.ssh`).
  - **Argument Sanitization**: Strips dangerous shell metacharacters (`;`, `&&`, `||`, `|`, `` ` ``, `$()`) when passing arguments to subprocesses.

---

## 7. Voice & Speech Engineering Pipeline

```
  Push-To-Talk / Mic
         │
         ▼
  sounddevice (16 kHz 16-bit Mono PCM)
         │
         ▼
  faster-whisper (CUDA FP16 / CPU INT8)
         │
         ▼ (Text & Language Tag)
  NyxAgent Brain (Ollama)
         │
         ▼ (Generated Response Text)
  Unicode Language Classifier (core/brain/language.py)
         │
         ├─────────────────────────────────────────┐
         │ (English)                               │ (Hindi / Marathi)
         ▼                                         ▼
   kokoro-onnx                               pyttsx3 + eSpeak-NG
  (82M Neural Model, CPU)                   (Phonemic Synthesizer, CPU)
         │                                         │
         └────────────────────┬────────────────────┘
                              │
                              ▼ (WAV Audio Bytes)
                    Web Audio API / Speaker
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
           Audio Output        AnalyserNode (FFT)
         (Headphones/Spk)               │
                                        ▼
                               Real-time Lip-Sync
                               & Viseme Animation
```

### Speech-to-Text: `faster-whisper`
- **Why We Use It**: `faster-whisper` is a reimplementation of OpenAI's Whisper model using **CTranslate2**, a fast inference engine for Transformer models. It is up to 4x faster than standard PyTorch Whisper while consuming significantly less memory.
- **How It Helps the Project**:
  - Runs in `float16` on CUDA (RTX 4050), transcribing spoken sentences in ~200-400 ms.
  - Automatically detects the spoken language (English, Hindi, Marathi).
  - Falls back automatically to `int8` CPU quantization on systems without dedicated NVIDIA GPUs.
  - Operates lazily on first invocation, keeping backend startup instantaneous.

### Audio Capture: `sounddevice`, `soundfile`, `numpy`
- **Why We Use It**: `sounddevice` provides Python bindings for the cross-platform PortAudio library, interfacing natively with modern Linux sound servers (PipeWire and PulseAudio).
- **How It Helps the Project**:
  - Captures microphone input cleanly at 16,000 Hz sample rate (the exact input format expected by Whisper, avoiding runtime resampling overhead).
  - Handles push-to-talk buffering and silence detection.

### Text-to-Speech Dual-Engine: `kokoro-onnx` & `pyttsx3`
- **Why We Use It**: No single TTS engine currently fulfills all requirements:
  - High-end neural models for Indian languages often require heavy GPU VRAM and multi-gigabyte models.
  - Low-end TTS engines sound robotic in English.
- **How It Helps the Project**:
  - **`kokoro-onnx` (English)**: An ultra-compact 82M parameter neural TTS model with remarkable voice quality and natural inflections (`af_heart`). By running on ONNX Runtime on the CPU, it synthesizes speech in near real-time without competing with Whisper or Ollama for GPU VRAM.
  - **`pyttsx3` + `espeak-ng` (Hindi / Marathi)**: Offline speech synthesizer that compiles text into native Indic phonemes with zero latency and negligible RAM usage.
  - **`NyxTTSSpeaker` Router**: Inspects the text language and routes each sentence to the optimal synthesizer automatically.

---

## 8. Multi-Tiered Memory Architecture

Human relationships depend on memory. NyxAI implements four distinct memory layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      4-LAYER MEMORY ARCHITECTURE                            │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│ Memory Layer     │ Storage Engine   │ Scope & Lifecycle│ Purpose            │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ Short-Term       │ aiosqlite        │ Session / Rolling│ Sliding window of  │
│                  │ (data/nyx_mem.db)│ conversation     │ recent messages    │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ Long-Term        │ aiosqlite        │ Persistent       │ Key-value facts    │
│                  │ (data/nyx_mem.db)│ across sessions  │ (name, likes, bio) │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ Episodic         │ aiosqlite        │ Persistent event │ Timestamped diary  │
│                  │ (data/nyx_mem.db)│ log / milestones │ of past events     │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ Semantic         │ ChromaDB +       │ Embedded vector  │ Similarity search  │
│                  │ nomic-embed-text │ search on disk   │ for relevant facts │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
```

1. **Short-Term Memory (`core/memory/short_term.py`)**: Stores active conversation dialogues in SQLite with token-aware sliding window truncation (`MAX_CONVERSATION_TOKENS=4096`), ensuring conversations stay within the LLM's context window.
2. **Long-Term Memory (`core/memory/long_term.py`)**: Stores user profile facts, preferences, and system parameters as typed key-value pairs (e.g., `user_name = "Rohan"`, `favorite_language = "Python"`). These are automatically injected into the system prompt.
3. **Episodic Memory (`core/memory/episodic.py`)**: A chronological journal of milestones, events, and completed tasks with ISO-8601 timestamps, allowing the companion to recall past shared moments.
4. **Semantic Memory (`core/memory/semantic.py`)**:
   - Uses **ChromaDB** as an embedded on-disk vector store.
   - Generates 768-dimensional vector embeddings using Ollama's local `nomic-embed-text` model.
   - Performs cosine similarity queries against historical memories, retrieving only the most contextually relevant past facts for the current conversation.

---

## 9. Desktop Shell & OS Integration

### Dedicated Native App: PyQt6 & PyQt6-WebEngine
- **Why We Use It**: Rather than packaging a bulky 200 MB Electron runtime that duplicates Chromium and Node.js processes, NyxAI uses PyQt6-WebEngine to leverage existing system Qt6 libraries on Linux.
- **How It Helps the Project**:
  - Creates a dedicated desktop window without browser URL bars or navigation buttons.
  - Automatically grants local microphone and audio permissions for seamless voice interaction without browser permission popups.
  - Integrates with the Linux system tray (`QSystemTrayIcon`) with controls to Show/Hide, toggle Always-on-Top, view backend health, and Quit.
  - Pre-configures Chromium flags (`--autoplay-policy=no-user-gesture-required --ignore-gpu-blocklist`) for instantaneous speech playback and smooth WebGL rendering under Wayland and X11.

### Single-Instance Lock via Unix Domain Sockets
- **Why We Use It**: If a user hits a desktop hotkey or clicks the application icon when the app is already open, starting a second full application instance wastes RAM and creates port collisions.
- **How It Helps the Project**:
  - `apps/desktop/desktop_app.py` opens a local socket at `/tmp/nyxai-desktop-app-instance`.
  - When a second instance launches (e.g. from the `nyxai` CLI or a desktop shortcut), it connects to the active socket, sends a `show` or `toggle` payload, and immediately terminates.
  - The running primary window receives the message and brings itself into focus.

### Linux Desktop Standards & systemd
- **Why We Use It**: Follows official Linux XDG and freedesktop.org specifications.
- **How It Helps the Project**:
  - **`deployment/desktop/nyxai.desktop`**: Installs into `~/.local/share/applications/`, making NyxAI discoverable in application menus across KDE Plasma, GNOME, XFCE, and rofi/wofi app launchers.
  - **`~/.local/bin/nyxai`**: CLI command supporting `nyxai app`, `toggle`, `start`, `stop`, `status`, `logs`.
  - **systemd user services (`nyxai-core.service`, `nyxai-ui.service`, `nyxai-voice.service`)**: Enables auto-start on user login without requiring root privileges, manages automatic restarts on failure, and captures clean unified logs in `journalctl`.
  - **Hyprland Window Manager Integration (`hyprctl`)**: Controls companion window positioning, workspace toggling, and binds push-to-talk directly to `SUPER+SPACE` and window toggle to `SUPER+J`.

---

## 10. Frontend Companion UI & Avatar Animation

```
                  apps/companion (React 18 + Vite)
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
     ▼                           ▼                           ▼
Photo Avatar Canvas      Stylized Girl Canvas        3D VRM Canvas
(MediaPipe 478 3D Mesh)  (SVG & Canvas Visemes)   (Three.js & three-vrm)
     │                           │                           │
     └───────────────────────────┼───────────────────────────┘
                                 │
                                 ▼
                     Web Audio API AnalyserNode
                      (Real-time FFT Lip Sync)
```

### React 18, TypeScript & Vite
- **Why We Use It**: React 18 delivers declarative UI rendering and fast state updates; TypeScript eliminates type errors across complex WebSocket event messages; Vite provides instantaneous sub-second dev server reloads and highly optimized production builds.
- **How It Helps the Project**: Powers the interactive Companion UI (`apps/companion`), including the conversation stream, memory viewer, audio visualizer, character customizer modal, and avatar viewport.

### Three.js & `@pixiv/three-vrm` (3D Companion)
- **Why We Use It**: VRM is the open standard 3D humanoid avatar format built on top of glTF 2.0. `@pixiv/three-vrm` is the official reference library for loading and animating VRM avatars in Three.js.
- **How It Helps the Project**:
  - Users can load any standard 3D `.vrm` or `.glb` model into NyxAI.
  - Supports spring-bone physics (natural hair and clothing movement), procedural eye blinking, gaze tracking towards the mouse cursor, and facial blend shapes (`aa`, `ih`, `ou`, `ee`, `oh`) synchronized with spoken audio.

### Google MediaPipe Vision (`@mediapipe/tasks-vision`) (Photo Avatar)
- **Why We Use It**: Many users prefer an avatar based on a real portrait photo rather than a 3D anime model. MediaPipe's `FaceLandmarker` detects 478 precise 3D facial landmarks directly in the browser via WebAssembly (`/mediapipe/wasm`), requiring no server-side GPU processing.
- **How It Helps the Project**:
  - In `apps/companion/src/utils/faceLandmarks.ts`, MediaPipe scans any uploaded girl portrait photo and locates the exact contours of the left eye, right eye, mouth, and chin.
  - `PhotoAvatarCanvas.tsx` uses these coordinates to dynamically deform canvas regions: closing eyelids for natural blinks at 60 FPS and modulating the mouth opening in real time as NyxAI speaks.

### Web Audio API (`useAudioLipSync.ts`)
- **Why We Use It**: Synthesizing audio on the backend and streaming it to the UI requires tight lip-sync synchronization on the client side.
- **How It Helps the Project**:
  - Decodes base64 WAV chunks into an `AudioBuffer` and routes playback through an `AudioContext` and `AnalyserNode`.
  - Runs a Fast Fourier Transform (FFT) during playback to calculate real-time frequency energy.
  - Dynamically calculates mouth opening percentages and classifies visemes (`closed`, `slight`, `open`, `wide`) at 60 frames per second, synchronizing avatar mouth animation with the spoken voice.

---

## 11. Model Fine-Tuning Pipeline

NyxAI includes a complete, self-contained fine-tuning pipeline in `training/` designed to customize model personality, conversational tone, and tool-calling precision.

```
Raw Dialogues / Datasets
          │
          ▼
training/scripts/dataset_builder.py
          │
          ▼ (Processed JSONL Dataset)
training/scripts/train_lora.py
  ├── bitsandbytes (4-bit NF4 Quantization)
  ├── PEFT (LoRA Rank=16, Alpha=32)
  ├── TRL (SFTTrainer)
  └── accelerate (Gradient Checkpointing)
          │
          ▼
training/scripts/export_model.py
          │
          ▼ (Merged GGUF Model)
Ollama Custom Model (ollama create nyxai)
```

- **Hugging Face `transformers` & `datasets`**: Handles model loading, tokenizer configuration, and batch streaming of training samples.
- **PEFT (Parameter-Efficient Fine-Tuning) with LoRA**: Rather than updating all 3 billion parameters, LoRA freezes the base weights and injects trainable low-rank decomposition matrices into the attention layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`), reducing trainable parameters by over 98%.
- **`bitsandbytes` (4-bit NormalFloat Quantization)**: Loads base model weights in 4-bit precision (QLoRA), slashing base model memory consumption to under 2.5 GB.
- **TRL (`SFTTrainer`) & `accelerate`**: Manages supervised fine-tuning loops with gradient checkpointing, enabling complete model training on a single 6 GB VRAM laptop GPU without out-of-memory errors.
- **Export & GGUF Quantization (`export_model.py`)**: Merges trained LoRA adapters back into base model weights and exports them for direct import into Ollama.

---

## 12. Testing, Code Quality & Automation

- **`pytest` & `pytest-asyncio`**: Comprehensive automated test suites across:
  - API routers and lifespan events (`api/tests/`)
  - Agent reasoning loops and tool execution (`tests/test_tools.py`)
  - Memory persistence and vector retrieval (`tests/`)
  - Avatar landmark detection and photo upload endpoints (`api/tests/test_avatar_api.py`)
  - System deployment and script validation (`tests/test_deployment.py`)
- **`ruff`**: Rust-powered Python linter and formatter that replaces Flake8, Black, and isort, running checks across the entire codebase in milliseconds (`make lint`).
- **`Makefile`**: Clean developer interface providing standardized commands: `make dev`, `make app`, `make voice`, `make test`, `make lint`, `make pull-model`, `make service-install`.
- **`scripts/install.sh`**: Intelligent cross-distro Linux installer that detects package managers (`pacman`, `apt`, `dnf`), installs system audio/Qt dependencies, sets up Python virtual environments, pulls Ollama models, builds the UI, and registers desktop shortcuts.

---

## 13. Summary: Why This Stack Fits NyxAI

| Requirement | Conventional Cloud Solution | NyxAI Local Stack | Technical Benefit |
|---|---|---|---|
| **Privacy** | OpenAI / Anthropic APIs | Local Ollama (`qwen2.5:3b`) | Zero data leakage, 100% offline functionality. |
| **Speech-to-Text** | Google Speech-to-Text API | `faster-whisper` (CUDA/CPU) | Zero subscription cost, sub-second latency, local audio. |
| **Text-to-Speech** | ElevenLabs / Azure Speech | `kokoro-onnx` + `pyttsx3` | Natural neural audio with zero cloud fees and zero GPU contention. |
| **Desktop Shell** | Heavy Electron Wrapper | PyQt6 + Qt6 WebEngine | Lower RAM usage, native Wayland/X11 support, instant startup. |
| **Visual Avatar** | Server-side video stream | Three.js + MediaPipe WASM | Client-side 60 FPS rendering, zero bandwidth consumption. |
| **Memory** | Cloud vector databases | SQLite + ChromaDB + Ollama | Instant local retrieval, zero recurring storage costs. |

By pairing optimized local neural inference with lightweight desktop frameworks, NyxAI delivers an AI companion that is responsive, expressive, completely private, and built specifically for the Linux desktop.

