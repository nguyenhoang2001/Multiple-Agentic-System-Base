"""
Runner – async interface between the FastAPI layer and the IoT pipeline.

The IoT pipeline is synchronous (LLM calls + smolagents sub-agents), so we
execute it in a background thread and stream chunks back to the caller via an
asyncio.Queue so the event loop stays unblocked.

Architecture change (vs previous version)
------------------------------------------
The previous version used a per-session ``CodeAgent`` (the master agent) to
orchestrate the full flow.  Small models hallucinated extra kwargs, wrote
comments instead of calling sub-agents, and used ``pass`` to skip steps.

The new version replaces the CodeAgent orchestrator with a deterministic Python
function ``run_iot_pipeline()`` that:
  1. Calls the LLM ONCE with Pydantic structured output to extract intent
  2. Checks Buffer Window Memory
  3. Delegates to clarification_agent (CodeAgent with tools) if info is missing
  4. Calls iterate_smart_home_yaml() deterministically
  5. Calls the LLM ONCE with Pydantic structured output to select devices
  6. Delegates to iot_action_agent (CodeAgent) for API execution

Multi-turn conversation
-----------------------
Chat history is loaded from the database and passed to ``_extract_intent()``
so follow-up messages (e.g. "phòng khách" after being asked which room) are
resolved correctly without relying on per-session agent memory.

Streaming strategy
------------------
``run_iot_pipeline()`` accepts an ``on_step`` callback.  Each step emits a
short status string (e.g. "Đang phân tích yêu cầu...\n") which the runner
forwards to the SSE queue immediately, giving the user live feedback while the
pipeline is running.  The final answer is sent as a ``FinalAnswer`` object.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from threading import Thread

from app.agent_system.memory.buffer_window import clear_buffer, set_current_session
from app.agent_system.orchestrator import run_iot_pipeline

logger = logging.getLogger(__name__)


@dataclass
class FinalAnswer:
    """The pipeline's final answer, distinct from raw step streaming text."""
    text: str


def clear_session(session_id: str) -> None:
    """Remove session buffer from cache (call on session delete)."""
    clear_buffer(session_id)


async def stream_response(
    message: str,
    history: list[dict],
    session_id: str | uuid.UUID,
) -> AsyncGenerator["str | FinalAnswer", None]:
    """
    Async generator that yields text chunks as the pipeline processes the query.

    Args:
        message:    The latest user message.
        history:    Prior turns as [{"role": "user"|"assistant", "content": str}].
                    Passed to intent extraction for multi-turn context resolution.
        session_id: Unique session identifier for Buffer Window Memory binding.

    Yields:
        str        – step status chunks (e.g. "Đang phân tích yêu cầu...\n")
        FinalAnswer – the pipeline's final answer string
    """
    sid = str(session_id)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | FinalAnswer | None] = asyncio.Queue()

    def _run() -> None:
        token = set_current_session(sid)
        try:
            final_text: str | None = None

            def on_step(text: str) -> None:
                """Forward step status text to the SSE queue immediately."""
                loop.call_soon_threadsafe(queue.put_nowait, text)

            # Run the deterministic IoT pipeline synchronously in this thread.
            # on_step streams intermediate status; the return value is the final answer.
            final_text = run_iot_pipeline(
                user_message=message,
                history=history,
                session_id=sid,
                on_step=on_step,
            )

            loop.call_soon_threadsafe(
                queue.put_nowait,
                FinalAnswer(text=final_text or "(No answer generated.)"),
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline raised an exception (session=%s)", sid)
            loop.call_soon_threadsafe(queue.put_nowait, f"Agent error: {exc}")
        finally:
            from app.agent_system.memory.buffer_window import current_session_id
            current_session_id.reset(token)
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    thread = Thread(target=_run, daemon=True)
    thread.start()

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk
