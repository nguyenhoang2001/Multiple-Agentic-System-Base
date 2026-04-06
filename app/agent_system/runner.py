"""
Runner – async interface between the FastAPI layer and the smolagents Manager Agent.

smolagents' CodeAgent.run() is synchronous, so we execute it in a background
thread and stream chunks back to the caller via an asyncio.Queue so the event
loop stays unblocked.

--- Official smolagents chat-history pattern ---
From the smolagents docs (GradioUI source + memory tutorial):

    # First turn – reset=True clears memory (default behaviour)
    agent.run(user_request, reset=True)

    # Subsequent turns in the same conversation – reset=False keeps memory
    agent.run(user_request, reset=False)

When reset=False, the agent preserves agent.memory.steps (TaskStep, ActionStep,
PlanningStep objects) so the model sees the full conversation history naturally.

Because multiple sessions can be active simultaneously we maintain a
per-session agent cache (_SESSION_AGENTS). Each session owns its own CodeAgent
instance so their memories never bleed into one another.

--- Streaming strategy ---
agent.run(stream=True) returns a generator that yields multiple object types
as execution progresses.  We handle each type differently:

  ChatMessageStreamDelta  – individual LLM tokens yielded *during* generation.
                            Pushing these gives real-time token-by-token output
                            so the user sees text appearing immediately instead
                            of waiting for the full step to finish.

  FinalAnswerStep         – yielded once at the very end; its `.output` is the
                            clean final answer string.  We use this to confirm
                            we have a final answer and send it if no tokens were
                            streamed (e.g. when stream_outputs is not supported).

  ActionStep / others     – skipped; their content already arrived via deltas
                            above, and re-sending observations causes duplicates.

A sentinel None signals the async generator to stop.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from threading import Thread

from dataclasses import dataclass

from smolagents import CodeAgent, ToolCallingAgent
from smolagents.models import ChatMessageStreamDelta
from smolagents.memory import FinalAnswerStep

from app.agent_system.orchestrator import manager_agent, _INSTRUCTIONS


@dataclass
class FinalAnswer:
    """The agent's executed final answer, distinct from raw LLM streaming tokens."""

    text: str


logger = logging.getLogger(__name__)

# Per-session agent cache  {session_id_str -> CodeAgent}
_SESSION_AGENTS: dict[str, CodeAgent] = {}


def _make_agent() -> CodeAgent:
    """Create a fresh per-session CodeAgent mirroring the manager_agent config."""
    agent = CodeAgent(
        tools=list(manager_agent.tools.values()),
        model=manager_agent.model,
        managed_agents=list(manager_agent.managed_agents.values()),
        max_steps=manager_agent.max_steps,
        additional_authorized_imports=manager_agent.authorized_imports,
        verbosity_level=manager_agent.logger.level,
        stream_outputs=True,  # stream code-execution print outputs
        code_block_tags="markdown",  # qwen3 outputs ```python blocks; align parser + system prompt
        instructions=_INSTRUCTIONS,
    )
    return agent


def _get_agent(session_id: str) -> tuple[CodeAgent, bool]:
    """
    Return (agent, is_new) for the given session.
    Creates a new agent the first time a session is seen.
    """
    if session_id not in _SESSION_AGENTS:
        _SESSION_AGENTS[session_id] = _make_agent()
        return _SESSION_AGENTS[session_id], True
    return _SESSION_AGENTS[session_id], False


def clear_session(session_id: str) -> None:
    """Remove a session's agent from the cache (call on session delete)."""
    _SESSION_AGENTS.pop(session_id, None)


async def stream_response(
    message: str,
    history: list[dict],
    session_id: str | uuid.UUID,
) -> AsyncGenerator["str | FinalAnswer", None]:
    """
    Async generator that yields text chunks as the agent processes the query.

    The official smolagents pattern for multi-turn conversation:
      - First turn  → agent.run(task, reset=True)   clears memory
      - Follow-ups  → agent.run(task, reset=False)  keeps memory

    Args:
        message:    The latest user message.
        history:    Prior turns as [{"role": "user"|"assistant", "content": str}].
                    Used only to decide whether this is a first turn (reset=True)
                    or a follow-up (reset=False). The actual history lives in
                    agent.memory.steps on the cached agent instance.
        session_id: Unique session identifier used to look up the cached agent.

    Yields:
        str – each text chunk (step observation or final answer).
    """
    sid = str(session_id)
    agent, is_new = _get_agent(sid)

    # reset=True on the first turn of a session; reset=False afterwards
    reset = is_new or not history

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Background thread: run the synchronous CodeAgent.run(stream=True).
    # The generator yields mixed types as each step executes:
    #   ChatMessageStreamDelta – push .content immediately (real-time tokens)
    #   FinalAnswerStep        – push .output as fallback / confirmation
    #   Everything else        – skip (ActionStep, PlanningStep, ToolCall ...)
    # ------------------------------------------------------------------
    def _run() -> None:
        try:
            streamed_any_delta = False
            final_answer_text: str | None = None

            for item in agent.run(message, stream=True, reset=reset):
                # 1. Real-time LLM token streaming
                if isinstance(item, ChatMessageStreamDelta):
                    if item.content:
                        loop.call_soon_threadsafe(queue.put_nowait, item.content)
                        streamed_any_delta = True

                # 2. Final answer arrived — always send it as a FinalAnswer
                #    object so the caller can store it separately from the
                #    raw thought/code streaming tokens.
                elif isinstance(item, FinalAnswerStep):
                    final_answer_text = (
                        str(item.output) if item.output is not None else ""
                    )
                    loop.call_soon_threadsafe(
                        queue.put_nowait, FinalAnswer(text=final_answer_text)
                    )

                # 3. Skip ActionStep, PlanningStep, ToolCall, ToolOutput,
                #    ActionOutput — content already covered by deltas above.

            if not streamed_any_delta and not final_answer_text:
                loop.call_soon_threadsafe(queue.put_nowait, "(No answer generated.)")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent raised an exception (session=%s)", sid)
            loop.call_soon_threadsafe(queue.put_nowait, f"Agent error: {exc}")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    thread = Thread(target=_run, daemon=True)
    thread.start()

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk
