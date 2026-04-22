"""
Retriever tools backed by the RAG store tiers:

1. ``RetrieverTool``          — semantic search over the static FAISS index
                                (automation rules, demonstration examples).
2. ``ConversationHistoryTool``— semantic search over asynchronously-embedded
                                conversation history (VectorStore-Backed Memory).
                                Defined in conversation_history_tool.py
"""

from __future__ import annotations

import logging

from smolagents import Tool

from app.vectore_store.store import get_vector_store
from app.agent_system.tools.conversation_history_tool import (
    ConversationHistoryTool,
    conversation_history_tool,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static knowledge retriever (rules, demonstrations)
# ---------------------------------------------------------------------------


class RetrieverTool(Tool):
    name = "retriever"
    description = (
        "Retrieves documents from the static IoT knowledge base using semantic similarity. "
        "The knowledge base contains automation rules and demonstration examples."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": (
                "The query to perform. This should be semantically close to your target "
                "documents. Use the affirmative form rather than a question."
            ),
        }
    }
    output_type = "string"

    def forward(self, query: str) -> str:
        assert isinstance(query, str), "Your search query must be a string"

        docs = get_vector_store().similarity_search(query, k=3)
        return "\nRetrieved documents:\n" + "".join(
            f"===== Document {i} =====\n{doc.page_content}\n"
            for i, doc in enumerate(docs)
        )


# ---------------------------------------------------------------------------
# Shared tool instances
# ---------------------------------------------------------------------------

huggingface_doc_retriever_tool = RetrieverTool()

__all__ = [
    "RetrieverTool",
    "ConversationHistoryTool",
    "huggingface_doc_retriever_tool",
    "conversation_history_tool",
]
