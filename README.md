# IoT Smart Home Agent System

A FastAPI application that orchestrates a **multi-agent AI system** to control and query smart home IoT devices via the CoreIoT (Thingsboard) API. All agents are powered by a local or cloud LLM via [smolagents](https://github.com/huggingface/smolagents).

---

## Architecture

```
User (HTTP / SSE)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                FastAPI  (app/main.py)                    │
│   POST /api/v1/chat/stream   (SSE)                       │
│   GET  /api/v1/sessions/{id}/history                     │
│   DELETE /api/v1/sessions/{id}                           │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│          Runner  (app/agent_system/runner.py)            │
│  • Per-session CodeAgent cache                           │
│  • Background thread + asyncio.Queue stream              │
│  • BufferWindowMemory session binding                    │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│          Manager Agent  (CodeAgent)                      │
│  Tools: iterate_smart_home_yaml, check_buffer_window     │
│  8-step orchestration flow                               │
└───────┬──────────────────┬────────────────┬─────────────┘
        │                  │                │
        ▼                  ▼                ▼
┌──────────────┐  ┌─────────────────┐  ┌───────────────────┐
│Clarification │  │ Retriever Agent │  │ IoT Action Agent  │
│    Agent     │  │ (device-selector│  │   (CodeAgent)     │
│(ToolCalling) │  │  ToolCalling,   │  │  read/post to     │
│buffer+yaml   │  │  no tools)      │  │  CoreIoT API      │
└──────────────┘  └─────────────────┘  └─────────┬─────────┘
                                                  │
                                                  ▼
                                        ┌──────────────────┐
                                        │  CoreIoT API     │
                                        │  (Thingsboard)   │
                                        │  GET/POST attrs  │
                                        └──────────────────┘
```

### 8-step flow

1. **Parse intent** — extract `room_name` and `type_device` from the message
2. **Check buffer** — `check_buffer_window()` looks up recently-used devices
3. **Clarify** — if info still missing, delegate to `clarification_agent` → return question to user
4. **Iterate YAML** — `iterate_smart_home_yaml(room_name, type_device)` fetches matching device config
5. **Select device** — `retriever_agent` parses the YAML and returns `[{name_device, token, room, shared_attributes}]`
6. **Execute** — `iot_action_agent` calls `post_shared_attributes` (write) or `read_shared_attributes` (read)
7. **Update buffer** — successful writes are recorded in `BufferWindowMemory` (per-session FIFO)
8. **Reply** — Vietnamese/English summary returned to user

---

## Component Overview

| Component | File | Purpose |
|---|---|---|
| **FastAPI app** | `app/main.py` | Entry point; pre-warms FAISS on startup |
| **Chat router** | `app/routers/chat.py` | SSE streaming endpoint + session history/delete |
| **Manager agent** | `app/agent_system/orchestrator.py` | Top-level `CodeAgent` — 8-step IoT orchestration |
| **Runner** | `app/agent_system/runner.py` | Async bridge; one `CodeAgent` per session |
| **LLM model** | `app/agent_system/model.py` | Shared `OpenAIServerModel` (Ollama local or cloud) |
| **Clarification agent** | `app/agent_system/agents/clarification_agent.py` | Resolves ambiguous device references |
| **Retriever agent** | `app/agent_system/agents/retriever_agent.py` | Selects exact device from YAML subset |
| **IoT action agent** | `app/agent_system/agents/iot_action_agent.py` | Executes CoreIoT read/write API calls |
| **Web agent** | `app/agent_system/agents/web_agent.py` | DuckDuckGo search for general questions |
| **YAML iterator** | `app/agent_system/tools/yaml_iterator.py` | Filters device config by room + type |
| **IoT action tools** | `app/agent_system/tools/iot_action_tools.py` | Tool wrappers for CoreIoT GET/POST |
| **Thingsboard API** | `app/agent_system/tools/thingsboard_api.py` | Raw HTTP helpers for CoreIoT |
| **Buffer window** | `app/agent_system/memory/buffer_window.py` | Per-session FIFO of recent device actions |
| **Vector store** | `app/vectore_store/` | FAISS with manifest-based auto-rebuild |
| **Knowledge base** | `knowledge_base/iot_knowledge/` | Automation rules + worked examples |
| **Device registry** | `knowledge_base/iot_knowledge/smart_home_configuration.yaml` | Tokens + rooms (never embedded) |
| **DB** | `app/repositories/` | PostgreSQL via SQLAlchemy async + Alembic |

---

## Quick Start

See [docs/running_the_app.md](docs/running_the_app.md) for the full step-by-step guide.

### Method 1: Using the Start Script (Recommended)

We provide a single script to automatically start the database, run migrations, and launch both the backend API and frontend web interface together.

```bash
# 1. Activate venv
source .IotAgent_venv/bin/activate

# 2. Install deps (First time only)
pip install -r requirements.txt

# 3. Configure env vars (First time only)
cp .env.example .env   # then edit with your values

# 4. Pull LLM (If using local)
ollama pull gemma4:e2b && ollama serve

# 5. Make the script executable and run it
chmod +x start.sh
./start.sh
```

**The system will be available at:**
* **Web Chat (Frontend):** `http://localhost:3000`
* **Backend API:** `http://localhost:8000`

*Press `Ctrl + C` to securely gracefully stop both the system and the database connection.*

---

### Method 2: Manual Setup

```bash
# 1. Activate venv
source .IotAgent_venv/bin/activate

# 2. Install deps
pip install -r requirements.txt

# 3. Configure
cp .env.example .env   # then edit with your values

# 4. Start PostgreSQL
docker compose up postgres -d

# 5. Pull LLM
ollama pull gemma4:e2b && ollama serve

# 6. Migrate DB
alembic upgrade head

# 7. Start server (FAISS builds automatically on first run)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 8. Start the web frontend (in a new terminal)
cd frontend
npm install
npm run dev
```

The web interface will be available at `http://localhost:3000`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/stream` | Stream agent reply via SSE |
| `GET` | `/api/v1/sessions/{id}/history` | Fetch conversation history |
| `DELETE` | `/api/v1/sessions/{id}` | Delete session |
| `GET` | `/api/v1/health` | Health check |

### curl example

```bash
SESSION_ID="00000000-0000-0000-0000-000000000001"

curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" -N \
  -d "{\"session_id\": \"$SESSION_ID\", \"user_id\": \"test\", \"message\": \"bật đèn trần phòng khách\"}"

curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" -N \
  -d "{\"session_id\": \"$SESSION_ID\", \"user_id\": \"test\", \"message\": \"TĂT đèn trần hồi nãy cho tôi\"}"
```

---

## LLM Modes

### Local Ollama (default)

```env
OLLAMA_MODE=local
LLM_MODEL_ID=gemma4:e2b
LLAMA_SERVER_URL=http://localhost:11434/v1
```

Recommended models: `gemma4:e2b`, `qwen3:1.7b`, `qwen3:4b`

### Ollama Cloud API

```env
OLLAMA_MODE=cloud
LLM_MODEL_ID=gpt-oss:20b-cloud
OLLAMA_API_KEY=<key from https://ollama.com/settings/keys>
```

---

## Knowledge Base

See [docs/vector_store_and_knowledge_base.md](docs/vector_store_and_knowledge_base.md) for details.

- `knowledge_base/iot_knowledge/rule/automation_rules.txt` — semantic rules → embedded into FAISS
- `knowledge_base/iot_knowledge/demonstration/examples.txt` — worked examples → embedded into FAISS
- `knowledge_base/iot_knowledge/smart_home_configuration.yaml` — device tokens → **NOT embedded**

The FAISS index auto-rebuilds when any `.txt` file changes (manifest-tracked).

---

## Project Structure

```
├── app/
│   ├── main.py
│   ├── agent_system/
│   │   ├── model.py                        # Shared LLM
│   │   ├── orchestrator.py                 # Master CodeAgent (8-step flow)
│   │   ├── runner.py                       # Async streaming bridge
│   │   ├── agents/
│   │   │   ├── clarification_agent.py      # Resolves ambiguous queries
│   │   │   ├── retriever_agent.py          # Device-selector from YAML
│   │   │   ├── iot_action_agent.py         # CoreIoT API executor
│   │   │   └── web_agent.py               # Web search
│   │   ├── tools/
│   │   │   ├── yaml_iterator.py           # YAML device filter
│   │   │   ├── iot_action_tools.py        # CoreIoT Tool wrappers
│   │   │   ├── thingsboard_api.py         # Raw HTTP helpers
│   │   │   ├── buffer_window_tools.py     # Buffer lookup tool
│   │   │   ├── retriever_tools.py         # FAISS retriever tool
│   │   │   ├── conversation_history_tool.py
│   │   │   └── web_tools.py
│   │   └── memory/
│   │       └── buffer_window.py           # Per-session action FIFO
│   ├── routers/
│   ├── vectore_store/
│   ├── db/
│   ├── models/
│   └── repositories/
├── knowledge_base/
│   ├── sources.py
│   └── iot_knowledge/
│       ├── smart_home_configuration.yaml  # Device registry (tokens)
│       ├── rule/automation_rules.txt
│       └── demonstration/examples.txt
├── faiss_index/                           # Auto-generated
├── alembic/
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + uvicorn |
| Agent framework | smolagents (HuggingFace) |
| LLM | Ollama (local) or Ollama Cloud |
| IoT platform | CoreIoT / Thingsboard |
| Vector search | FAISS + LangChain |
| Embeddings | sentence-transformers (HuggingFace) |
| Database | PostgreSQL + SQLAlchemy async + Alembic |
| Streaming | Server-Sent Events via `sse-starlette` |
