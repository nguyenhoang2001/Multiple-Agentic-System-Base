# Vector Store & Knowledge Base

This document explains how the RAG pipeline works, what is (and is not) embedded,
and how to update the knowledge base.

---

## Overview

```
knowledge_base/
├── sources.py                          ← loads .txt files for embedding (edit this)
└── iot_knowledge/
    ├── smart_home_configuration.yaml   ← device registry (tokens, rooms) — NOT embedded
    ├── rule/
    │   └── automation_rules.txt        ← automation rules → embedded into FAISS
    └── demonstration/
        └── examples.txt               ← worked examples → embedded into FAISS

faiss_index/                            ← auto-generated (do not commit)
    ├── index.faiss
    ├── index.pkl
    └── manifest.json                   ← tracks file mtimes for auto-rebuild

app/vectore_store/
├── embeddings.py   ← HuggingFace sentence-transformers embedding model
├── builder.py      ← chunks + embeds + saves to faiss_index/
├── loader.py       ← loads index from faiss_index/
└── store.py        ← singleton with manifest-based auto-rebuild
```

---

## What is and is NOT embedded

| File | Embedded? | Why |
|---|---|---|
| `rule/automation_rules.txt` | ✅ Yes | Semantic rules for the retriever |
| `demonstration/examples.txt` | ✅ Yes | Worked examples for few-shot retrieval |
| `smart_home_configuration.yaml` | ❌ No | Device tokens are secret — accessed directly by `yaml_iterator.py` |

> **Never embed `smart_home_configuration.yaml`** — it contains device access tokens
> that would then be retrievable via semantic search by any query.

---

## Auto-rebuild on file change

`store.py` computes a manifest `{relative_path: mtime}` for every `.txt` file under
`knowledge_base/iot_knowledge/` and writes it to `faiss_index/manifest.json`.

On every `get_vector_store()` call:
1. Compute current manifest.
2. Compare against saved `manifest.json`.
3. If different (file added, edited, or deleted) → rebuild and save.
4. If same → load from disk (fast path).

This means you can edit `automation_rules.txt` or `examples.txt` and restart the
server — the index updates automatically.

---

## How to update the knowledge base

### Edit existing rules or examples

1. Open `knowledge_base/iot_knowledge/rule/automation_rules.txt` or
   `knowledge_base/iot_knowledge/demonstration/examples.txt`.
2. Make changes and save.
3. Restart the server — the FAISS index rebuilds automatically.

### Add a new .txt file

Drop any `.txt` file into `knowledge_base/iot_knowledge/rule/` or
`knowledge_base/iot_knowledge/demonstration/`. It will be picked up on the next
server start (or `get_vector_store()` call).

### Add a new device

Edit `knowledge_base/iot_knowledge/smart_home_configuration.yaml`:

```yaml
rooms:
  - name: bedroom
    type_device:
      - name_type: smart_light
        devices:
          - name: Đèn ngủ
            device_token: <your_coreiot_token>
            description_location: bedside table
            shared_attributes:
              - name_key: led
                value: boolean
                description: on/off switch
```

Then update `automation_rules.txt` and `examples.txt` to document the new device,
and restart the server to rebuild the FAISS index.

---

## How the pipeline works

```
knowledge_base/sources.py  (DirectoryLoader over rule/ + demonstration/)
        │
        │  load_documents() → List[Document]
        ▼
app/vectore_store/builder.py
        │  split (CHUNK_SIZE=200, CHUNK_OVERLAP=20) → embed → FAISS
        ▼
faiss_index/   (persisted to disk)
        │
        ▼
app/vectore_store/store.py  get_vector_store()
        │
        ▼
app/agent_system/tools/retriever_tools.py  RetrieverTool.forward()
        │  similarity_search(query, k=3)
        ▼
clarification_agent  (context for device-type resolution)
```

Note: `retriever_agent` (device-selector) does **not** use FAISS — it receives
the YAML subset inline from the Master Agent and parses it directly.

---

## Force a manual rebuild

```bash
rm -rf faiss_index/
python3 -c "from app.vectore_store.store import get_vector_store; get_vector_store()"
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FAISS_INDEX_PATH` | `faiss_index` | Where the FAISS index is saved/loaded |
| `EMBEDDING_MODEL_NAME` | `thenlper/gte-small` | HuggingFace embedding model |
| `CHUNK_SIZE` | `200` | Token chunk size for text splitting |
| `CHUNK_OVERLAP` | `20` | Overlap between consecutive chunks |
