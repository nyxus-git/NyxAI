# NyxAI — Product Requirements Document

## 1. Product Overview

### Product Name

NyxAI

### Product Vision

NyxAI is a local-first AI companion and intelligent desktop agent designed for Linux.

The product combines:

* Conversational AI
* Voice interaction
* Hindi, Marathi, English, and Hinglish communication
* Local LLM inference
* Animated AI companion
* Desktop automation
* Tool calling
* Long-term memory
* Task execution
* AI agent capabilities
* Local fine-tuning experiments

The primary goal is to create an AI companion that feels natural and friendly while also functioning as a useful AI agent capable of completing tasks on the user's Linux computer.

NyxAI should behave as a combination of:

1. AI assistant
2. Conversational companion
3. Linux desktop agent
4. Voice assistant
5. Personal productivity assistant

The system must prioritize user control, privacy, security, modularity, and extensibility.

---

# 2. Target Platform

## Primary Operating System

Arch Linux-based distributions.

Initial development environment:

* EndeavourOS
* Arch Linux
* Hyprland
* Wayland

## Initial Hardware Target

Development hardware:

* Intel Core i7-14700HX
* NVIDIA RTX 4050 Laptop GPU
* Approximately 6 GB VRAM
* 16 GB RAM
* 1920x1200 display
* NVIDIA CUDA support

The application must be optimized for consumer hardware with limited VRAM.

The architecture must avoid requiring a large GPU for normal usage.

---

# 3. Core Product Experience

The desired user experience is:

The computer is running normally.

NyxAI runs quietly in the background.

The user presses a global keyboard shortcut.

Example:

SUPER + J

The companion interface opens.

A full-screen animated AI character appears.

The character greets the user naturally.

Example:

"Hey! काय चाललंय?"

The user can talk naturally using voice or text.

NyxAI listens, understands the request, and responds.

If necessary, NyxAI can execute tasks using approved tools.

Example interactions:

"VS Code उघड."

"Open Firefox."

"Play some relaxing music."

"Search YouTube for an AI system design tutorial."

"आज आपण काय काम करायचं होतं?"

"आज mood थोडा खराब आहे."

The assistant should be capable of both friendly conversation and productive task execution.

---

# 4. Product Principles

NyxAI must follow these principles.

## Local First

Whenever practical, AI processing should run locally.

Examples:

* Local LLM
* Local memory
* Local speech recognition
* Local database

Cloud APIs should be optional rather than mandatory.

---

## Privacy

The user should have control over:

* Microphone access
* Memory storage
* Conversation history
* External APIs
* Internet access
* System permissions

The system must clearly distinguish between local processing and external processing.

---

## Safety

The LLM must never directly receive unrestricted shell execution capability.

All system actions must pass through:

1. Tool schema validation
2. Permission classification
3. Safety validation
4. User confirmation when required

---

## Modular Architecture

Each major component must be independently replaceable.

Examples:

The user should be able to replace:

* LLM
* STT engine
* TTS engine
* Memory database
* Avatar frontend
* Vector database

without redesigning the entire application.

---

# 5. User Personas

## Persona 1: AI Developer

The user wants:

* Local LLM experimentation
* Fine-tuning
* Agent development
* Linux automation
* AI project experimentation

---

## Persona 2: Daily Computer User

The user wants to:

* Open applications
* Search information
* Play music
* Manage tasks
* Talk with an AI assistant

using natural language.

---

# 6. Functional Requirements

## FR-1: Conversational AI

NyxAI must support natural conversation.

Supported languages:

* English
* Hindi
* Marathi
* Hinglish
* Mixed-language conversations

Example:

User:

"आज NyxAI वर काम करूया."

Assistant:

"Done! आज कोणत्या feature वर काम करायचं?"

The assistant should maintain context across the current conversation.

---

## FR-2: Companion Personality

NyxAI should have a consistent personality.

Desired characteristics:

* Friendly
* Supportive
* Playful
* Intelligent
* Curious
* Honest
* Emotionally expressive
* Not overly dramatic
* Not manipulative
* Not possessive

The assistant may communicate casually.

Examples:

"अरे, that's actually a pretty good idea."

"चल, step by step करूया."

"आज थोडा break घेणं useful वाटतंय."

The assistant must never pretend to be a human.

The assistant may express conversational warmth, but must remain clear that it is an AI system.

---

# 7. AI Modes

NyxAI must support three conceptual modes.

## Companion Mode

Purpose:

Natural conversation.

Capabilities:

* Casual conversation
* Friendly interaction
* Discussion
* Encouragement
* Reflection

---

## Assistant Mode

Purpose:

Answer questions and help with work.

Examples:

* Explain AI concepts
* Explain programming
* Search information
* Summarize content

---

## Agent Mode

Purpose:

Execute multi-step tasks.

Example:

User:

"Search for FastAPI tutorials and open the best beginner video."

Agent workflow:

1. Understand task
2. Create plan
3. Search
4. Select relevant result
5. Request permission if required
6. Execute action
7. Report result

---

# 8. Local LLM System

## Requirements

The system must support local LLM inference.

The LLM interface must be abstracted.

Example interface:

LLMProvider

Methods:

* generate()
* chat()
* structured_output()
* stream()
* embeddings()

Initial implementation may use Ollama.

Future implementations may support:

* llama.cpp
* vLLM where hardware permits
* Hugging Face inference
* External APIs

---

## Recommended Model Strategy

Because the target machine has approximately 6 GB VRAM:

Primary models should initially be:

* Approximately 3B parameters
* Approximately 4B parameters

Larger models may be supported through:

* Quantization
* CPU/GPU hybrid inference

Model selection must be configurable.

---

# 9. Agent Architecture

The AI agent must not directly execute arbitrary commands.

Architecture:

User Request

↓

LLM

↓

Structured Intent

↓

Tool Selection

↓

Tool Arguments

↓

Schema Validation

↓

Safety Validation

↓

Permission Check

↓

Tool Execution

↓

Result

↓

LLM Response

---

## Tool Example

User:

"Open Firefox."

LLM output:

{
"tool": "open_application",
"arguments": {
"application": "firefox"
}
}

The backend validates the request before execution.

---

# 10. Tool System

All tools must implement a standard interface.

Example:

Tool:

name

description

input_schema

permission_level

execute()

---

## Initial Tools

### System Tools

* Get battery status
* Get CPU usage
* Get RAM usage
* Get GPU status
* Get current time
* Get system information

---

### Application Tools

* Open application
* Focus application
* Close application

Closing applications should require appropriate confirmation.

---

### Browser Tools

* Open URL
* Search web
* Open search result
* Search YouTube

---

### Music Tools

Initial capabilities:

* Search music
* Open music platform
* Play requested music where integration permits

---

### File Tools

* Search files
* Open files
* Read supported documents
* Organize files only with appropriate confirmation

---

### Task Tools

* Create task
* List tasks
* Mark task complete
* Set reminder

---

# 11. Voice System

The voice pipeline must be modular.

Architecture:

Microphone

↓

Voice Activity Detection

↓

Speech-to-Text

↓

Language Detection

↓

Conversation / Agent System

↓

Response Generation

↓

Text-to-Speech

↓

Speaker

---

# 12. Speech-to-Text

Initial implementation should support:

* English
* Hindi
* Marathi

The STT provider must be replaceable.

Potential implementations include:

* Whisper-based systems
* faster-whisper
* Other local multilingual speech recognition systems

Requirements:

* Streaming or near-real-time processing
* Background noise tolerance
* Multilingual recognition

---

# 13. Text-to-Speech

The TTS system should support a natural feminine voice where legally and technically available.

Priority languages:

1. Hindi
2. Marathi
3. English

The TTS engine must support future replacement.

Requirements:

* Streaming audio
* Low latency
* Configurable voice
* Configurable speech speed
* Configurable emotional tone where supported

The application must only use voices and models that are properly licensed.

---

# 14. Wake Word System

Wake word support should be implemented after the basic push-to-talk system works.

Example:

"Hey Nyx"

Requirements:

* Low CPU usage
* Local processing
* Privacy-focused
* Configurable enable/disable option

---

# 15. Push-to-Talk

The first implementation should support a keyboard shortcut.

Example:

Hold:

SUPER + SPACE

Behavior:

Press

↓

Microphone recording starts

↓

Release

↓

Speech processing begins

↓

AI responds

This should be implemented before continuous wake word listening.

---

# 16. Full-Screen Companion Interface

A global shortcut should toggle the companion interface.

Example:

SUPER + J

Behavior:

Normal desktop

↓

SUPER + J

↓

Full-screen companion interface opens

↓

Animated avatar appears

↓

Voice conversation becomes available

↓

SUPER + J

↓

Interface closes or minimizes

The backend must remain running.

The UI must not require restarting the AI system.

---

# 17. Avatar System

The avatar system must be separated from the AI backend.

The avatar should react to AI state.

States:

* idle
* listening
* thinking
* speaking
* happy
* excited
* confused
* concerned

The backend should publish events.

Example:

{
"event": "avatar_state",
"state": "thinking"
}

The frontend should subscribe to these events.

---

# 18. Lip Synchronization

Initial implementation:

Simple audio-based mouth movement.

Example:

Audio amplitude

↓

Mouth open value

↓

Avatar animation

Future implementation:

Phoneme-based lip synchronization.

---

# 19. Memory System

Memory must be divided into layers.

## Short-Term Memory

Current conversation context.

Storage duration should be configurable.

---

## Long-Term Memory

Important user-approved information.

Examples:

* User preferences
* Long-term projects
* Important goals

The user must be able to:

* View memory
* Edit memory
* Delete memory
* Disable memory

---

## Episodic Memory

Stores important events.

Example:

"Started NyxAI project."

"Completed first LoRA training experiment."

---

## Semantic Memory

Stores information learned from documents or knowledge sources.

This should eventually use:

Embeddings

*

Vector database

---

# 20. Memory Retrieval

The system should not send all historical memories to the LLM.

Workflow:

User message

↓

Generate query embedding

↓

Search relevant memories

↓

Retrieve top results

↓

Filter

↓

Inject relevant context

↓

Generate response

---

# 21. Fine-Tuning System

Fine-tuning is an advanced component.

It must not be required for the first working version.

The training system should support:

* Dataset preparation
* Dataset validation
* LoRA
* QLoRA
* Training experiments
* Model evaluation

---

# 22. Fine-Tuning Use Cases

Fine-tuning may eventually improve:

* Structured tool calling
* Hindi/Hinglish/Marathi assistant behavior
* Domain-specific Linux assistance
* Consistent response formatting

Fine-tuning should not be used for:

* Dynamic information
* User memory
* Application state

Those should use tools or retrieval.

---

# 23. Training Dataset Format

Preferred format:

JSONL

Example:

{
"messages": [
{
"role": "system",
"content": "You are NyxAI."
},
{
"role": "user",
"content": "VS Code उघड."
},
{
"role": "assistant",
"content": "{"tool":"open_application","arguments":{"application":"code"}}"
}
]
}

Dataset categories:

* Tool calling
* Linux tasks
* Hindi conversations
* Marathi conversations
* Hinglish conversations
* Safety scenarios
* Multi-step planning

---

# 24. Safety Architecture

Actions must have permission levels.

## Level 1: Safe

Automatically allowed.

Examples:

* Get battery
* Get time
* Read system information

---

## Level 2: Confirmation

Requires user approval.

Examples:

* Open external website
* Install package
* Close application
* Modify files

---

## Level 3: High Risk

Requires explicit confirmation and additional validation.

Examples:

* System configuration changes
* Service management
* Privileged operations

---

## Level 4: Blocked

Never automatically execute.

Examples include dangerous or destructive operations.

---

# 25. Architecture

The application should use a multi-component architecture.

Components:

1. Companion UI
2. API / Core service
3. LLM service
4. Agent service
5. Voice service
6. Memory service
7. Tool system
8. Safety layer

Communication should use:

* HTTP for request/response APIs
* WebSocket for real-time events
* Internal Python interfaces where appropriate

---

# 26. Suggested Technology Stack

## Backend

Python

FastAPI

Pydantic

---

## Local AI

Ollama initially.

Model provider abstraction for future engines.

---

## LLM Training

Hugging Face ecosystem.

Potential tools:

* Transformers
* PEFT
* TRL
* Accelerate

LoRA and QLoRA for efficient fine-tuning.

---

## Speech Recognition

Initial evaluation:

faster-whisper or another suitable multilingual local STT engine.

---

## Frontend

Recommended:

TypeScript

React

Vite

The avatar frontend should communicate with the backend through WebSocket.

---

## Database

Initial:

SQLite

Later:

PostgreSQL if required.

---

## Vector Search

Start simple.

Possible later options:

* Chroma
* Qdrant
* FAISS

The vector database must be abstracted.

---

## Deployment

systemd user services.

The application should start automatically after login.

---

# 27. System Startup Architecture

Computer Login

↓

systemd user service

↓

NyxAI Core starts

↓

LLM connection initializes

↓

Memory initializes

↓

Agent initializes

↓

Voice system waits

↓

Global shortcut becomes active

↓

User activates NyxAI

The user must not need to manually run:

python main.py

for normal daily use.

---

# 28. Development Phases

## Phase 1: Foundation

Goals:

* Project setup
* Python environment
* Local LLM
* Basic conversation
* Basic FastAPI backend

Success criteria:

User sends text.

↓

Local LLM responds.

---

## Phase 2: Agent Tools

Goals:

* Tool registry
* Structured tool calling
* Validation
* Basic system tools

Success criteria:

User:

"What's my battery?"

↓

Agent selects tool.

↓

Tool executes.

↓

Response returned.

---

## Phase 3: Voice

Goals:

* Push-to-talk
* Speech recognition
* Text-to-speech

Success criteria:

User speaks.

↓

NyxAI understands.

↓

NyxAI responds with voice.

---

## Phase 4: Companion UI

Goals:

* Full-screen interface
* Global shortcut
* Animated avatar
* AI state synchronization

Success criteria:

SUPER + J

↓

Companion appears.

↓

Avatar reacts to conversation.

---

## Phase 5: Memory

Goals:

* Short-term memory
* Long-term memory
* Episodic memory
* User memory controls

---

## Phase 6: Advanced Agent

Goals:

* Multi-step planning
* Task execution
* Browser interaction
* File tools

---

## Phase 7: Fine-Tuning

Goals:

* Dataset engineering
* LoRA
* QLoRA
* Tool calling fine-tuning
* Evaluation

---

## Phase 8: Persistent Deployment

Goals:

* systemd services
* Automatic startup
* Error recovery
* Logging
* Configuration

---

# 29. Non-Functional Requirements

## Performance

The assistant should remain responsive.

Target:

Basic actions should feel interactive.

The UI must not freeze while the LLM is generating.

---

## Reliability

Services should automatically restart after crashes where appropriate.

---

## Observability

The system should include:

* Structured logs
* Error logs
* Service health checks

---

## Configuration

Configuration should be stored separately from code.

Example:

config.yaml

or environment variables.

Secrets must never be committed to Git.

---

# 30. Testing

The project must include:

Unit tests for:

* Tool validation
* Permission logic
* Memory logic
* Agent routing

Integration tests for:

* API
* LLM provider abstraction
* Tool execution

---

# 31. Evaluation

The AI system should eventually include evaluation datasets.

Evaluate:

* Tool selection accuracy
* Argument accuracy
* Language handling
* Safety behavior
* Response latency

Example metrics:

Tool Accuracy

Argument Accuracy

Task Completion Rate

Average Latency

Safety Violation Rate

---

# 32. MVP Definition

The first MVP must include only:

1. Local LLM
2. Text conversation
3. FastAPI backend
4. Tool calling
5. Battery tool
6. Open application tool
7. Basic browser search
8. SQLite conversation history
9. Basic push-to-talk
10. Basic TTS

The animated avatar is not required for the first MVP.

---

# 33. MVP Success Scenario

The user starts the computer.

NyxAI backend automatically starts.

The user activates the interface.

The user says:

"Hey, VS Code उघड आणि NyxAI project open कर."

NyxAI:

1. Understands the request.
2. Selects the appropriate tools.
3. Opens VS Code.
4. Opens the project folder.
5. Responds in Marathi or the user's preferred language.

---

# 34. Future Vision

NyxAI may eventually become a complete local AI operating companion.

Potential future features:

* Screen understanding
* Camera vision with explicit user control
* Multi-agent architecture
* Advanced planning
* Calendar integration
* Email integration
* Document intelligence
* Proactive reminders
* Personal knowledge graph
* Fine-tuned specialized models
* More advanced animated avatar
* Cross-device synchronization

The architecture must allow these features without requiring a complete rewrite.

---

# 35. AI Coding Agent Implementation Rules

The coding agent must follow these rules.

1. Do not build the entire system in one file.

2. Keep modules small and focused.

3. Use interfaces and abstractions.

4. Add logging.

5. Add type hints.

6. Add error handling.

7. Do not give unrestricted shell access to the LLM.

8. Validate all tool arguments.

9. Implement features incrementally.

10. Write tests for critical logic.

11. Do not implement fine-tuning before the base system works.

12. Build a working MVP before advanced avatar features.

13. Prefer local processing where practical.

14. Do not hard-code model names.

15. Keep all providers configurable.

---

# 36. First Development Task

The first task for the AI coding agent is:

Create the NyxAI backend foundation.

Requirements:

1. Python project setup.
2. FastAPI application.
3. Health endpoint.
4. Configuration management.
5. LLM provider abstraction.
6. Ollama provider implementation.
7. Basic chat endpoint.
8. Structured logging.
9. Basic tests.

Success criteria:

GET /health

returns:

{
"status": "healthy"
}

POST /chat

accepts:

{
"message": "Hello NyxAI"
}

The backend sends the message to the configured local LLM.

The response is returned through the API.

Do not implement voice, avatar, fine-tuning, or advanced agent features in the first development task.

Build the foundation correctly first.
