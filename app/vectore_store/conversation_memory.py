"""VectorStore-Backed Conversation Memory.

Uses LangChain's ``VectorStoreRetrieverMemory`` to asynchronously embed and
persist conversation history in a dedicated FAISS vector store per session.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

from langchain_classic.memory import VectorStoreRetrieverMemory
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.vectore_store.embeddings import get_embeddings

logger = logging.getLogger(__name__)

CONVERSATION_MEMORY_PATH: str = os.environ.get(
    "CONVERSATION_MEMORY_PATH", "faiss_index/conversation_memory"
)

# Module-level dictionary to hold store per session_id
_memory_stores: dict[str, FAISS] = {}
_memories: dict[str, VectorStoreRetrieverMemory] = {}


def _get_or_create_store(session_id: str) -> FAISS:
    """Return the FAISS store for conversation history per session_id."""
    if session_id in _memory_stores:
        return _memory_stores[session_id]

    embeddings = get_embeddings()
    session_path = os.path.join(CONVERSATION_MEMORY_PATH, session_id)
    index_file = os.path.join(session_path, "index.faiss")

    if os.path.isfile(index_file):
        logger.info(f"Loading conversation memory store for session {session_id}.")
        store = FAISS.load_local(
            session_path,
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
        )
        _memory_stores[session_id] = store
    else:
        logger.info(f"Initialising new in-memory history store for {session_id}.")
        store = FAISS.from_documents(
            [
                Document(
                    page_content="Conversation history store initialised.",
                    metadata={"type": "init"},
                )
            ],
            embedding=embeddings,
        )
        _memory_stores[session_id] = store

    return _memory_stores[session_id]


def get_conversation_memory(session_id: str) -> VectorStoreRetrieverMemory:
    """Return the shared VectorStoreRetrieverMemory per session."""
    if session_id in _memories:
        return _memories[session_id]

    store = _get_or_create_store(session_id)
    retriever = store.as_retriever(search_kwargs={"k": 5})
    memory = VectorStoreRetrieverMemory(
        retriever=retriever,
        memory_key="conversation_history",
        return_docs=False,
    )
    _memories[session_id] = memory
    return memory


def _sync_save_conversation(
    inputs: Dict[str, Any],
    outputs: Dict[str, str],
    session_id: str,
) -> None:
    try:
        memory = get_conversation_memory(session_id)
        memory.save_context(inputs, outputs)

        store = _get_or_create_store(session_id)
        session_path = os.path.join(CONVERSATION_MEMORY_PATH, session_id)
        os.makedirs(session_path, exist_ok=True)
        store.save_local(session_path)
    except Exception as exc:
        logger.error(f"Failed to save conversation turn: {exc}")


async def async_save_conversation(
    inputs: Dict[str, Any],
    outputs: Dict[str, str],
    session_id: str,
) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_save_conversation, inputs, outputs, session_id)


def load_conversation_context(query: str, session_id: str) -> str:
    memory = get_conversation_memory(session_id)
    variables = memory.load_memory_variables({"prompt": query})
    history: str = variables.get("conversation_history", "")

    if not history or "Conversation history store initialised" in history:
        return "No relevant conversation history found."

    return f"Relevant past conversations:\n{history}"
