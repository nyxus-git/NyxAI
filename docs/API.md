# NyxAI — API Documentation

This document describes the REST, WebSocket, and Desktop IPC interfaces exposed by NyxAI.

---

## 1. REST Endpoints

Base URL: `http://127.0.0.1:8000`

### 1.1 Health Check
```http
GET /health
```
Returns system status and LLM connectivity details.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5:3b",
    "healthy": true
  },
  "timestamp": "2026-09-08T17:35:00Z"
}
```

---

### 1.2 Chat & Agent Interaction
```http
POST /chat
```
Send a message to NyxAI in companion or agent mode.

**Request Body**:
```json
{
  "message": "What is my current battery level?",
  "mode": "agent",
  "conversation_id": "optional-uuid"
}
```

**Parameters**:
- `message` (*string, required*): Input text from user (English, Hindi, Marathi, Hinglish).
- `mode` (*string, optional*): `"companion"` (conversational) or `"agent"` (tools enabled). Default: `"companion"`.
- `conversation_id` (*string, optional*): ID for conversational history continuity.

**Response `200 OK`**:
```json
{
  "reply": "Your battery is currently at 85% and discharging.",
  "mode": "agent",
  "conversation_id": "abc-123",
  "tool_used": "get_battery_status",
  "tool_result": {
    "percentage": 85,
    "plugged_in": false
  }
}
```

---

### 1.3 Memory System Endpoints

#### List Long-Term Memories
```http
GET /memory/long-term
```
Returns all stored key-value facts and preferences.

#### Save Long-Term Memory
```http
POST /memory/long-term
```
**Request Body**:
```json
{
  "key": "user_name",
  "value": "Rohan",
  "category": "personal"
}
```

#### Delete Long-Term Memory
```http
DELETE /memory/long-term/{key}
```

#### List Episodic Memories
```http
GET /memory/episodic?limit=20
```

#### Log Episodic Event
```http
POST /memory/episodic
```
**Request Body**:
```json
{
  "event": "Completed Phase 8 persistent deployment setup."
}
```

---

## 2. Real-Time Voice WebSocket

```http
GET /voice (Upgrade: websocket)
```
Used by the Companion UI and desktop clients for real-time audio interaction.

### Client Messages:
```json
{
  "type": "audio",
  "data": "<base64-encoded-wav-bytes>",
  "mode": "agent"
}
```

### Server Events Emitted:
1. `{"event": "transcript", "text": "What's my battery?", "language": "en"}`
2. `{"event": "avatar_state", "state": "thinking"}`
3. `{"event": "response", "text": "Your battery is at 85%.", "audio": "<base64-wav>"}`
4. `{"event": "avatar_state", "state": "speaking"}`
5. `{"event": "avatar_state", "state": "idle"}`

---

## 3. Desktop IPC Socket

Socket Path: `/tmp/nyxai-desktop.sock`

Line-delimited JSON commands processed by `apps/desktop/main.py daemon`:
- `toggle-ui`: Triggers Wayland / Hyprland window focus or launches browser app mode.
- `status`: Returns running status of backend and desktop controller.
