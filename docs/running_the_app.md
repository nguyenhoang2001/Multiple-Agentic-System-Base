# Running the App

This guide explains how to start the IoT smart home agent system from scratch.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | With a virtual environment |
| PostgreSQL | Used to persist conversation history |
| Ollama | Runs the local LLM (gemma4:e2b or qwen3:1.7b) |
| CoreIoT / Thingsboard account | For actual device control |

---

## 1 — Set up the environment

```bash
# Activate virtual environment (create it once with: python3 -m venv .IotAgent_venv)
source .IotAgent_venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 2 — Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mars

# LLM — local Ollama (default)
OLLAMA_MODE=local
LLM_MODEL_ID=gemma4:e2b
LLAMA_SERVER_URL=http://localhost:11434/v1

# Embedding model (FAISS)
EMBEDDING_MODEL_NAME=google/embedding-gecko-300m
FAISS_INDEX_PATH=faiss_index

# CoreIoT API
COREIOT_API_BASE=https://app.coreiot.io
```

> **Cloud Ollama** (optional): set `OLLAMA_MODE=cloud`, add `OLLAMA_API_KEY=<key>`,
> and set `LLM_MODEL_ID=gpt-oss:20b-cloud`.

---

## 3 — Start services

```bash
# PostgreSQL via Docker
docker compose up postgres -d

# Pull the Ollama model (first time only)
ollama pull gemma4:e2b   # or qwen3:1.7b

# Keep Ollama running
ollama serve
```

---

## 4 — Run DB migrations

```bash
alembic upgrade head
```

---

## 5 — Start the API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On first startup the FAISS vector store is automatically built from
`knowledge_base/iot_knowledge/rule/` and `knowledge_base/iot_knowledge/demonstration/`.
You will see log output like:

```
Building FAISS index from knowledge_base/iot_knowledge/...
FAISS index saved → faiss_index/
```

Once running, API docs are at:
- Swagger UI → http://localhost:8000/docs
- ReDoc → http://localhost:8000/redoc

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/stream` | Stream an agent reply via SSE |
| `GET` | `/api/v1/sessions/{session_id}/history` | Fetch full message history |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete a session and its messages |
| `GET` | `/api/v1/health` | Health check |

---

## POST /api/v1/chat/stream

### Request body

```json
{
  "session_id": "00000000-0000-0000-0000-000000000001",
  "user_id": "test",
  "message": "bật đèn trần phòng khách"
}
```

| Field | Type | Description |
|---|---|---|
| `session_id` | UUID v4 | Unique conversation ID — reuse across turns for multi-turn chat |
| `user_id` | string | User identifier |
| `message` | string | The message to send |

### SSE event types

| Event | Payload | Description |
|---|---|---|
| `agent.message.delta` | `{"text": "..."}` | One streaming token chunk |
| `agent.message.done` | `{"session_id": "..."}` | Reply complete and persisted |
| `agent.workflow.failed` | `{"error": "..."}` | Unhandled error |
| `heartbeat` | `{}` | Keepalive every 15 s |

---

## curl Examples

Use a fixed session ID for easy testing:

```bash
SESSION_ID="00000000-0000-0000-0000-000000000001"
```

### Control a device

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" -N \
  -d "{\"session_id\": \"$SESSION_ID\", \"user_id\": \"test\", \"message\": \"bật đèn trần phòng khách\"}"
```

### Read device status

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" -N \
  -d "{\"session_id\": \"$SESSION_ID\", \"user_id\": \"test\", \"message\": \"đèn trần đang bật hay tắt?\"}"
```

### Trigger clarification (no room specified)

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" -N \
  -d "{\"session_id\": \"$SESSION_ID\", \"user_id\": \"test\", \"message\": \"bật đèn\"}"
```

The agent will ask which room to clarify ambiguity.

### Get conversation history

```bash
curl "http://localhost:8000/api/v1/sessions/$SESSION_ID/history?user_id=test"
```

### Delete a session

```bash
curl -X DELETE "http://localhost:8000/api/v1/sessions/$SESSION_ID?user_id=test"
```

---

## Rebuilding the FAISS index

The index auto-rebuilds whenever any `.txt` file under `knowledge_base/iot_knowledge/` changes
(tracked via `faiss_index/manifest.json`). To force a rebuild manually:

```bash
rm -rf faiss_index/
python3 -c "from app.vectore_store.store import get_vector_store; get_vector_store()"
```
