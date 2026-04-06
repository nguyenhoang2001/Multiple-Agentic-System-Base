"""
Shared LLM model used by all agents in the system.
SDK: smolagents OpenAIServerModel (OpenAI-compatible API)

--- Two modes, controlled by .env ---

MODE 1 — Local Ollama (default, qwen3:1.7b)
    OLLAMA_MODE=local
    LLAMA_SERVER_URL=http://localhost:11434/v1   (Ollama's OpenAI-compatible endpoint)
    LLM_MODEL_ID=qwen3:1.7b

    Start the model locally first:
        ollama pull qwen3:1.7b
        ollama serve

MODE 2 — Ollama Cloud API (no local download, large cloud models only)
    OLLAMA_MODE=cloud
    OLLAMA_API_KEY=your_key_from_https://ollama.com/settings/keys
    LLM_MODEL_ID=gpt-oss:20b-cloud   (or deepseek-v3.1:671b-cloud, qwen3-coder:480b-cloud)

    Available cloud models: https://ollama.com/search?c=cloud

Note: qwen3:1.7b is a small local model — cloud mode is for models too large to run locally.
"""

import os

from smolagents import OpenAIServerModel

_mode = os.environ.get("OLLAMA_MODE", "local").lower()

if _mode == "cloud":
    model = OpenAIServerModel(
        model_id=os.environ.get("LLM_MODEL_ID", "gpt-oss:20b-cloud"),
        api_base="https://ollama.com/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", ""),
    )
else:
    # Local Ollama — pull the model first: ollama pull qwen3:1.7b
    model = OpenAIServerModel(
        model_id=os.environ.get("LLM_MODEL_ID", "qwen3:1.7b"),
        api_base=os.environ.get("LLAMA_SERVER_URL", "http://localhost:11434/v1"),
        api_key="ollama",  # required by client, ignored by Ollama
        max_tokens=4096,  # smaller context window for local model
    )
