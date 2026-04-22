"""
Web Agent — web search using DuckDuckGo.

Uses ToolCallingAgent instead of CodeAgent so the model outputs a JSON
tool call instead of generating Python code.
"""

from smolagents import ToolCallingAgent

from app.agent_system.model import model
from app.agent_system.tools.web_tools import search_tool

web_agent = ToolCallingAgent(
    tools=[search_tool],
    model=model,
    max_steps=2,
    verbosity_level=1,
    stream_outputs=True,
    name="search_agent",
    description="Runs web searches for you. Give it your query as an argument.",
)
