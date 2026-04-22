"""Shared vector store singleton.

Provides a single ``get_vector_store()`` entry point used by retriever tools.
On first call it tries to load a persisted index from disk; if none exists or
if the source files have changed since the last build it rebuilds automatically.

Auto-rebuild logic (diagram: "Tự động Embed khi có file mới")
-------------------------------------------------------------
A manifest file ``faiss_index/manifest.json`` records the mtime of every .txt
file under ``knowledge_base/iot_knowledge/``. On each cold start the current
mtimes are compared with the manifest. If any file is new, deleted, or modified
the index is rebuilt and the manifest updated. This keeps the FAISS index in
sync without manual intervention.

Typical usage
-------------
    from app.vectore_store.store import get_vector_store

    vs = get_vector_store()
    results = vs.similarity_search("automation rules", k=3)
"""

from __future__ import annotations

import json
import logging
import os

from langchain_community.vectorstores import FAISS

from app.vectore_store.builder import build_and_save, FAISS_INDEX_PATH
from app.vectore_store.loader import index_exists, load_vector_store

logger = logging.getLogger(__name__)

_store: FAISS | None = None

_KNOWLEDGE_ROOT = os.environ.get(
    "IOT_KNOWLEDGE_PATH", "knowledge_base/iot_knowledge"
)
_MANIFEST_PATH = os.path.join(FAISS_INDEX_PATH, "manifest.json")


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _compute_manifest(root: str) -> dict[str, float]:
    """Walk *root* recursively and return ``{relpath: mtime}`` for every .txt file."""
    manifest: dict[str, float] = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith(".txt"):
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, start=".")
                manifest[rel] = os.path.getmtime(full)
    return manifest


def _read_manifest() -> dict[str, float]:
    """Return the persisted manifest or empty dict if not found."""
    if not os.path.isfile(_MANIFEST_PATH):
        return {}
    try:
        with open(_MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_manifest(manifest: dict[str, float]) -> None:
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    with open(_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _manifest_changed(current: dict[str, float], saved: dict[str, float]) -> bool:
    return current != saved


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_vector_store() -> FAISS:
    """
    Return the shared FAISS vector store (lazy singleton).

    Load order:
    1. Return cached in-memory instance if already initialised.
    2. Check manifest — if source .txt files changed, rebuild.
    3. Load from local disk if ``faiss_index/`` exists and manifest is current.
    4. Build from scratch and save to disk.
    """
    global _store

    if _store is not None:
        return _store

    current_manifest = _compute_manifest(_KNOWLEDGE_ROOT)
    saved_manifest = _read_manifest()

    if index_exists() and not _manifest_changed(current_manifest, saved_manifest):
        _store = load_vector_store()
        logger.info("FAISS index loaded from disk (manifest unchanged).")
    else:
        if index_exists():
            logger.info(
                "Knowledge files changed — rebuilding FAISS index."
            )
        else:
            logger.warning(
                "No local FAISS index found — building from scratch. "
                "This may take a few minutes."
            )
        _store = build_and_save()
        _write_manifest(current_manifest)

    return _store


def reset_vector_store() -> None:
    """Clear the in-memory cache (useful for testing or after re-indexing)."""
    global _store
    _store = None
