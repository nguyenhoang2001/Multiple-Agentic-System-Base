"""
ConversationHistoryTool — VectorStore-Backed conversation memory retriever.

Performs semantic search over asynchronously-embedded conversation history.
Maps to the "Async embedding — conversation history" tier of the IoT RAG store architecture.
"""

from __future__ import annotations

from smolagents import Tool

from app.vectore_store.conversation_memory import load_conversation_context


class ConversationHistoryTool(Tool):
    name = "conversation_history_retriever"
    description = (
        "Retrieves semantically relevant past conversation turns from the "
        "VectorStore-Backed conversation memory. Use this to recall what the user "
        "previously asked or what settings they previously configured."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": (
                "A description of what you are trying to recall from past conversations, "
                "e.g. 'What temperature did the user set last time?' or "
                "'Previous commands for the living room light'."
            ),
        }
    }
    output_type = "string"

    def forward(self, query: str) -> str:
        from app.agent_system.memory.buffer_window import get_current_buffer
        assert isinstance(query, str), "Your search query must be a string"
        buf = get_current_buffer()
        session_id = buf.session_id if buf else "default"
        return load_conversation_context(query, session_id)


conversation_history_tool = ConversationHistoryTool()
