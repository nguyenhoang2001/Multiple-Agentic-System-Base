"""
Shared LLM model used by all agents in the system.
SDK: smolagents OpenAIServerModel (OpenAI-compatible API)

--- Two modes, controlled by .env ---

MODE 1 — Local Ollama (default, gemma4:e2b)
    OLLAMA_MODE=local
    LLAMA_SERVER_URL=http://localhost:11434/v1
    LLM_MODEL_ID=gemma4:e2b

    Start the model locally first:
        ollama pull gemma4:e2b
        ollama serve

MODE 2 — Ollama Cloud API
    OLLAMA_MODE=cloud
    OLLAMA_API_KEY=your_key_from_https://ollama.com/settings/keys
    LLM_MODEL_ID=gpt-oss:20b-cloud

--- Thinking mode (gemma4 / qwen3) ---
gemma4:e2b enables thinking via the <|think|> token in the system prompt.
Passing extra_body={"think": False} through the OpenAI-compatible client
tells Ollama to skip that token so the model only generates the final
output — no <think>...</think> blocks.
Ref: https://ollama.com/library/gemma4:e2b
"""

import os

from smolagents import OpenAIServerModel

_mode = os.environ.get("OLLAMA_MODE", "local").lower()
_model_id = os.environ.get("LLM_MODEL_ID", "gemma4:e2b")

# extra_body is forwarded verbatim into the HTTP request body by the OpenAI
# Python client. Ollama uses it to suppress the <|think|> token for gemma4/qwen3.
_no_think = {"extra_body": {"think": False}}

if _mode == "cloud":
    model = OpenAIServerModel(
        model_id=_model_id,
        api_base="https://ollama.com/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", ""),
        **_no_think,
    )
    thinking_model = OpenAIServerModel(
        model_id=_model_id,
        api_base="https://ollama.com/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", ""),
    )
else:
    model = OpenAIServerModel(
        model_id=_model_id,
        api_base=os.environ.get("LLAMA_SERVER_URL", "http://localhost:11434/v1"),
        api_key="ollama",
        **_no_think,
    )
    thinking_model = OpenAIServerModel(
        model_id=_model_id,
        api_base=os.environ.get("LLAMA_SERVER_URL", "http://localhost:11434/v1"),
        api_key="ollama",
    )
