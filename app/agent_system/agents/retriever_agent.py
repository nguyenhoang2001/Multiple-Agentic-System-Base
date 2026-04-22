"""
Retriever Agent — Device Selector

Architecture note
-----------------
Device selection is implemented as a direct LLM call with Pydantic structured
output (JSON mode) in ``app/agent_system/orchestrator._select_devices()``.

Using a CodeAgent here was unreliable: small local models (gemma4:e2b) would
attempt to parse the YAML programmatically (json.loads on YAML text, wrong
attribute index selection, hallucinated kwargs like mode="request").

The deterministic flow is now:
  iterate_smart_home_yaml(room, type) → yaml_subset (str)
      ↓
  _select_devices(user_message, yaml_subset)
      → LLM call with response_format={"type": "json_object"}
      → validated via DeviceActionList Pydantic model
      → List[DeviceAction]
      ↓
  iot_action_agent.run(devices_json)  ← only CodeAgent in the pipeline

This file is kept as a reference/import stub so external code that imports
``retriever_agent`` doesn't break.  The actual logic lives in the orchestrator.
"""

# The retriever logic is in orchestrator._select_devices().
# Nothing to import here — this module is intentionally empty.
