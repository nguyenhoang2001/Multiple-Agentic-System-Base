"""
Retriever tools backed by the three RAG store tiers:

1. ``RetrieverTool``          — semantic search over the static FAISS index
                                (device registry, sensor knowledge, rules, demonstrations).
2. ``SensorLogsTool``         — live sensor readings via the smart home hub API.
                                Defined in sensor_logs_tool.py
3. ``ConversationHistoryTool``— semantic search over asynchronously-embedded
                                conversation history (VectorStore-Backed Memory).
                                Defined in conversation_history_tool.py
"""

from __future__ import annotations

import logging

from smolagents import Tool

from app.vectore_store.store import get_vector_store
from app.agent_system.tools.sensor_logs_tool import SensorLogsTool, sensor_logs_tool
from app.agent_system.tools.conversation_history_tool import (
    ConversationHistoryTool,
    conversation_history_tool,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Static knowledge retriever (device registry, rules, sensor knowledge, demos)
# ---------------------------------------------------------------------------


class RetrieverTool(Tool):
    name = "retriever"
    description = (
        "Retrieves documents from the static IoT knowledge base using semantic similarity. "
        "The knowledge base contains device registry, sensor knowledge, automation rules, "
        "and demonstration examples."
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

        docs_with_scores = get_vector_store().similarity_search_with_score(query, k=5)
        # Sort by score (lower = more similar) and take top 2
        docs_with_scores.sort(key=lambda x: x[1])
        top_docs = docs_with_scores[:2]

        return "\nRetrieved documents (ranked by relevance):\n" + "".join(
            f"===== Document {i + 1} (score: {score:.4f}) =====\n{doc.page_content}\n"
            for i, (doc, score) in enumerate(top_docs)
        )


# ---------------------------------------------------------------------------
# Shared tool instances
# ---------------------------------------------------------------------------

doc_retriever_tool = RetrieverTool()

__all__ = [
    "RetrieverTool",
    "SensorLogsTool",
    "ConversationHistoryTool",
    "doc_retriever_tool",
    "sensor_logs_tool",
    "conversation_history_tool",
]
