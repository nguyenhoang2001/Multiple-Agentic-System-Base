"""Document sources for the IoT Smart Home RAG knowledge base.

This is the single place to define what gets indexed into the static FAISS
vector store. Add, remove, or replace sources here — the builder will pick
them up automatically on the next run. The vector store auto-rebuilds when
any .txt file under ``knowledge_base/iot_knowledge/`` changes (mtime check
in ``app/vectore_store/store.py``).

Static knowledge (embedded once, auto-rebuilt on change)
---------------------------------------------------------
- ``rule/``         — automation rules (triggers, conditions, actions)
- ``demonstration/``— worked examples: user request → CoreIoT API call

Note: The device registry is in ``smart_home_configuration.json`` and is
NEVER embedded into FAISS. Agents query it live via ``iterate_smart_home_yaml_tool``.
Conversation history is async-embedded separately by ``conversation_memory``.

Typical usage
-------------
    from knowledge_base.sources import load_documents

    docs = load_documents()
"""

from __future__ import annotations

import logging
import os
from typing import List

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

IOT_KNOWLEDGE_PATH: str = os.environ.get(
    "IOT_KNOWLEDGE_PATH", "knowledge_base/iot_knowledge"
)

_SUBDIRS: dict[str, str] = {
    "rule": "rule",
    "demonstration": "demonstration",
}


def _load_subdir(subdir_name: str, source_tag: str) -> List[Document]:
    """Load all .txt files from a subdirectory and tag them with *source_tag*."""
    path = os.path.join(IOT_KNOWLEDGE_PATH, subdir_name)
    if not os.path.isdir(path):
        logger.warning("Knowledge subdir not found, skipping: '%s'", path)
        return []

    loader = DirectoryLoader(
        path,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
        silent_errors=True,
    )
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = source_tag
    logger.info(
        "Loaded %d document(s) from '%s/' (tag=%s).", len(docs), subdir_name, source_tag
    )
    return docs


def load_documents() -> List[Document]:
    """
    Return all LangChain Documents to be indexed into the static FAISS store.

    Called by the vector store builder. Extend ``_SUBDIRS`` to add more
    static knowledge sources.
    """
    docs: List[Document] = []
    for subdir_name, source_tag in _SUBDIRS.items():
        docs.extend(_load_subdir(subdir_name, source_tag))

    logger.info("Total static documents collected: %d", len(docs))
    return docs
