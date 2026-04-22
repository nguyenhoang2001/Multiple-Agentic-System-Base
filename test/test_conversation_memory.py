"""
Tests for conversation_memory.py — VectorStore-Backed conversation memory.

Scenarios are all IoT smart home interactions: lighting, temperature, locks, etc.
The test suite uses a temporary directory for the FAISS index so it never
touches the real faiss_index/ on disk.
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """
    Redirect the conversation memory FAISS index to a temporary directory and
    reset module-level singletons before each test so tests are independent.
    """
    memory_path = str(tmp_path / "conversation_memory")
    monkeypatch.setenv("CONVERSATION_MEMORY_PATH", memory_path)

    # Reset module singletons so each test starts with a fresh store
    import app.vectore_store.conversation_memory as cm

    cm._memory_store = None
    cm._memory = None
    # Reload the path constant from the patched env var
    cm.CONVERSATION_MEMORY_PATH = memory_path

    yield

    # Teardown: reset singletons again after each test
    cm._memory_store = None
    cm._memory = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _save(inputs: dict, outputs: dict) -> None:
    """Synchronous wrapper around the async save for use in sync tests."""
    from app.vectore_store.conversation_memory import _sync_save_conversation

    _sync_save_conversation(inputs, outputs)


# ---------------------------------------------------------------------------
# Unit tests — sync save & retrieve
# ---------------------------------------------------------------------------


class TestSaveAndRetrieve:

    def test_single_turn_is_retrievable(self):
        """A saved conversation turn can be retrieved with a related query."""
        from app.vectore_store.conversation_memory import load_conversation_context

        _save(
            inputs={"input": "Turn on the living room lights"},
            outputs={"output": "Living room lights turned on at 80% brightness."},
        )

        result = load_conversation_context("living room lights brightness")
        assert "living room" in result.lower()

    def test_temperature_command_is_retrievable(self):
        """A thermostat command turn appears in results for a temperature query."""
        from app.vectore_store.conversation_memory import load_conversation_context

        _save(
            inputs={"input": "Set the thermostat to 22 degrees"},
            outputs={"output": "Thermostat set to 22°C in heating mode."},
        )

        result = load_conversation_context("thermostat temperature setpoint")
        assert "No relevant" not in result

    def test_multiple_turns_stored_and_retrieved(self):
        """Multiple turns are stored and the most relevant one is returned."""
        from app.vectore_store.conversation_memory import load_conversation_context

        _save(
            inputs={"input": "Lock the front door"},
            outputs={"output": "Front door locked successfully."},
        )
        _save(
            inputs={"input": "Turn off the kitchen lights"},
            outputs={"output": "Kitchen lights turned off."},
        )
        _save(
            inputs={"input": "What is the CO2 level in the living room?"},
            outputs={"output": "CO2 level in the living room is 820 ppm — moderate."},
        )

        result = load_conversation_context("front door lock status")
        assert "No relevant" not in result
        assert "door" in result.lower()

    def test_semantic_match_not_exact_keyword(self):
        """Retrieval finds semantically related content, not just exact keyword match."""
        from app.vectore_store.conversation_memory import load_conversation_context

        _save(
            inputs={"input": "It's too bright in here"},
            outputs={"output": "Dimmed the living room light to 30% brightness."},
        )

        # Query uses 'luminosity' not 'bright' — should still match semantically
        result = load_conversation_context("reduce luminosity in the room")
        assert "No relevant" not in result

    def test_empty_store_returns_no_history_message(self):
        """Fresh store (only init placeholder) returns the 'no history' message."""
        from app.vectore_store.conversation_memory import load_conversation_context

        result = load_conversation_context("living room temperature")
        assert result == "No relevant conversation history found."


# ---------------------------------------------------------------------------
# Unit tests — persistence (save to disk and reload)
# ---------------------------------------------------------------------------


class TestPersistence:

    def test_store_persists_to_disk_after_save(self, tmp_path):
        """After a save, the FAISS index files exist on disk."""
        import app.vectore_store.conversation_memory as cm

        _save(
            inputs={"input": "Open the blinds in the living room"},
            outputs={"output": "Living room blinds opened to 100%."},
        )

        index_file = os.path.join(cm.CONVERSATION_MEMORY_PATH, "index.faiss")
        assert os.path.isfile(index_file), "FAISS index file should exist after save"

    def test_history_survives_singleton_reset(self):
        """History written in one session is retrievable after singletons are reset."""
        import app.vectore_store.conversation_memory as cm
        from app.vectore_store.conversation_memory import load_conversation_context

        _save(
            inputs={"input": "Is the bedroom window sensor triggered?"},
            outputs={"output": "No motion detected on the bedroom window sensor."},
        )

        # Simulate an app restart — clear the in-memory singletons
        memory_path = cm.CONVERSATION_MEMORY_PATH
        cm._memory_store = None
        cm._memory = None

        # The store should reload from disk
        result = load_conversation_context("bedroom window sensor motion")
        assert "No relevant" not in result


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncSave:

    @pytest.mark.asyncio
    async def test_async_save_does_not_block_and_is_retrievable(self):
        """async_save_conversation completes and the turn becomes retrievable."""
        from app.vectore_store.conversation_memory import (
            async_save_conversation,
            load_conversation_context,
        )

        await async_save_conversation(
            inputs={"input": "Goodnight, turn everything off"},
            outputs={
                "output": (
                    "Goodnight! Lights off, thermostat set to 19°C, "
                    "front door locked."
                )
            },
        )

        result = load_conversation_context("night mode lights thermostat")
        assert "No relevant" not in result

    @pytest.mark.asyncio
    async def test_async_save_multiple_turns_sequentially(self):
        """Multiple async saves accumulate correctly in the store."""
        from app.vectore_store.conversation_memory import (
            async_save_conversation,
            load_conversation_context,
        )

        turns = [
            (
                {"input": "What is the humidity in the bedroom?"},
                {"output": "Bedroom humidity is 55% — within comfortable range."},
            ),
            (
                {"input": "Turn on the air purifier"},
                {"output": "Air purifier turned on. AQI monitoring active."},
            ),
            (
                {"input": "Set a movie scene"},
                {"output": "Movie mode: lights dimmed to 20%, blinds closed, TV on."},
            ),
        ]

        for inp, out in turns:
            await async_save_conversation(inputs=inp, outputs=out)

        humidity_result = load_conversation_context("bedroom humidity level")
        assert "No relevant" not in humidity_result

        movie_result = load_conversation_context("movie scene lighting")
        assert "No relevant" not in movie_result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_save_does_not_raise_on_long_input(self):
        """Very long conversation turns are handled without error."""
        from app.vectore_store.conversation_memory import load_conversation_context

        long_reply = (
            "The sensor readings across all rooms are as follows: "
            + "; ".join(
                f"room_{i}: temperature=21.{i}°C, humidity=5{i}%" for i in range(20)
            )
        )
        _save(
            inputs={"input": "Give me a full report of all sensors"},
            outputs={"output": long_reply},
        )

        result = load_conversation_context("sensor report all rooms")
        assert "No relevant" not in result

    def test_save_error_does_not_propagate(self, monkeypatch):
        """A failure inside save is caught and does not raise to the caller."""
        import app.vectore_store.conversation_memory as cm

        # Force get_conversation_memory to raise
        monkeypatch.setattr(
            cm,
            "get_conversation_memory",
            lambda: (_ for _ in ()).throw(RuntimeError("forced")),
        )

        # Should not raise
        cm._sync_save_conversation(
            inputs={"input": "Turn on the porch light"},
            outputs={"output": "Porch light turned on."},
        )
