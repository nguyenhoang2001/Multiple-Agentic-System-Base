"""
Managed Clarification Agent

Called as the FIRST step by the orchestrator for every user query.
Determines whether the query is clear or ambiguous.

- CLEAR: The query specifies a device and action (or a clear knowledge question).
  Returns "CLEAR: <original query>" so the orchestrator can route it.
- UNCLEAR: The query is vague or missing key info.
  Uses conversation history and knowledge base to suggest a specific action,
  then asks the user to confirm.
"""

from smolagents import ToolCallingAgent

from app.agent_system.model import model
from app.agent_system.tools.retriever_tools import (
    doc_retriever_tool,
    conversation_history_tool,
)

_CLARIFICATION_INSTRUCTIONS = """\
You are a clarification gate for an IoT smart home system.
You are called FIRST for every user message. Your job is to decide if the query is CLEAR or UNCLEAR.

## CLEAR queries (return immediately — do NOT call any tools):
A query is CLEAR if it meets ANY of these:
  - Mentions a specific device AND a specific action: "turn on the bedroom light", "set thermostat to 22"
  - Mentions a specific device AND asks for a value: "what is the bedroom temperature?", "how bright is the living room light?"
  - Is a general knowledge question: "what sensors are supported?", "how does the thermostat work?"

For CLEAR queries, return EXACTLY this format (no tools needed):
  CLEAR: <repeat the original user message exactly>

Examples:
  User: "turn on the living room light" → return "CLEAR: turn on the living room light"
  User: "what is the bedroom temperature?" → return "CLEAR: what is the bedroom temperature?"
  User: "what devices do I have?" → return "CLEAR: what devices do I have?"

## UNCLEAR queries (use tools to clarify):
A query is UNCLEAR if:
  - It uses pronouns without context: "turn it on", "turn that off"
  - It describes a feeling without specifying a device: "I'm cold", "it's too hot", "it's dark"
  - It mentions an action but no device: "make it brighter", "turn everything off"

For UNCLEAR queries, follow these steps:
1. Call `conversation_history_retriever` with the user's message to check if earlier turns mention a device or location.
2. Call `retriever` to look up available devices that could match the user's intent.
3. Based on what you found, suggest a CONCRETE action and ask the user to confirm.
   Keep it short (1-2 sentences). Do NOT execute commands. Do NOT return device IDs or API calls.

Good UNCLEAR response examples:
  "It sounds like you want to increase the bedroom thermostat. Would you like me to set it to 22°C?"
  "Did you mean to turn on the living room light or the bedroom light?"
  "Would you like me to raise the thermostat temperature to warm up?"
"""

clarification_agent = ToolCallingAgent(
    tools=[conversation_history_tool, doc_retriever_tool],
    model=model,
    max_steps=3,
    verbosity_level=1,
    stream_outputs=True,
    name="clarification_agent",
    description=(
        "Checks if the user query is clear or ambiguous. Called FIRST for every message. "
        "If CLEAR, returns 'CLEAR: <query>' so the orchestrator can route to the right agent. "
        "If UNCLEAR, checks conversation history and available devices to suggest a specific "
        "action and asks the user to confirm."
    ),
    instructions=_CLARIFICATION_INSTRUCTIONS,
)
