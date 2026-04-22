import re

with open("app/agent_system/orchestrator.py", "r") as f:
    code = f.read()

old_code = """    # ------------------------------------------------------------------
    # Step 1 — Extract intent (Pydantic structured output, no code gen)
    # ------------------------------------------------------------------
    emit("Orchestrator", "Analyzing request...")
    intent = _extract_intent(user_message, session_id=session_id, history=history)
    logger.info("Extracted intent: room=%s type=%s", intent.room_name, intent.type_device)

    # ------------------------------------------------------------------
    # Step 2 — Check Buffer Window Memory
    # ------------------------------------------------------------------
    cached = check_buffer_window_tool.forward(user_message)
    if cached != "[]":
        try:
            hit = json.loads(cached)[0]
            if intent.room_name is None:
                intent.room_name = hit.get("room")
            if intent.type_device is None:
                intent.type_device = hit.get("type_device") or None
            emit(
                "Orchestrator",
                f"Buffer Memory: {hit.get('device_name')} "
                f"({hit.get('room')})"
            )
            logger.debug("Buffer hit: %s", hit)
        except (json.JSONDecodeError, IndexError, KeyError):
            pass

    # ------------------------------------------------------------------
    # Step 3 — Clarify if info still missing
    # ------------------------------------------------------------------
    if intent.room_name is None or intent.type_device is None:
        emit("Orchestrator", "Need more information...")
        question = clarification_agent.run(user_message, intent)
        return f"Clarification_Agent: {str(question)}"

    emit("Orchestrator", f"Room: {intent.room_name} | Device: {intent.type_device}")

    # ------------------------------------------------------------------
    # Step 4 — Iterate YAML → focused subset (deterministic, no LLM)
    # ------------------------------------------------------------------
    yaml_subset = iterate_smart_home_yaml(
        room_name=None if intent.room_name == "all" else intent.room_name,
        type_device=None if intent.type_device == "all" else intent.type_device,
    )
    if yaml_subset.strip() == "rooms: []":
        return (
            f"Orchestrator: Could not find device '{intent.type_device}' "
            f"in '{intent.room_name}'."
        )

    # ------------------------------------------------------------------
    # Step 5 — Select target device(s) (Pydantic structured output)
    # ------------------------------------------------------------------
    emit("Orchestrator", "Selecting devices...")
    devices = _select_devices(user_message, yaml_subset, intent, session_id=session_id)"""

new_code = """    # ------------------------------------------------------------------
    # Step 1 — Extract intent (Pydantic structured output, no code gen)
    # ------------------------------------------------------------------
    emit("Orchestrator", "Analyzing request...")
    intent_list = _extract_intent(user_message, session_id=session_id, history=history)
    for idx, i in enumerate(intent_list.intents):
        logger.info("Extracted intent %d: room=%s type=%s", idx+1, i.room_name, i.type_device)

    # ------------------------------------------------------------------
    # Step 2 — Check Buffer Window Memory (applied to the first intent if missing)
    # ------------------------------------------------------------------
    cached = check_buffer_window_tool.forward(user_message)
    if cached != "[]":
        try:
            hit = json.loads(cached)[0]
            for i in intent_list.intents:
                if i.room_name is None:
                    i.room_name = hit.get("room")
                if i.type_device is None:
                    i.type_device = hit.get("type_device") or None
            emit("Orchestrator", f"Buffer Memory applied: {hit.get('device_name')} ({hit.get('room')})")
        except (json.JSONDecodeError, IndexError, KeyError):
            pass

    # ------------------------------------------------------------------
    # Step 3 — Clarify if info still missing
    # ------------------------------------------------------------------
    for i in intent_list.intents:
        if i.room_name is None or i.type_device is None:
            emit("Orchestrator", "Need more information...")
            question = clarification_agent.run(user_message, i)
            return f"Clarification_Agent: {str(question)}"
            
    emit("Orchestrator", f"Handling {len(intent_list.intents)} intents.")

    # ------------------------------------------------------------------
    # Step 4 — Iterate YAML → focused subset (deterministic, no LLM)
    # ------------------------------------------------------------------
    merged_yaml_subset = ""
    for i in intent_list.intents:
        subset = iterate_smart_home_yaml(
            room_name=None if i.room_name == "all" else i.room_name,
            type_device=None if i.type_device == "all" else i.type_device,
        )
        # Avoid duplicate yaml inclusions if they overlap
        if subset not in merged_yaml_subset:
            merged_yaml_subset += subset + "\\n"
            
    if not merged_yaml_subset or "rooms: []" in merged_yaml_subset.strip():
        # It's possible partial overlaps exist, but if it's completely empty:
        if len(intent_list.intents) == 1:
            return f"Orchestrator: Could not find device '{intent_list.intents[0].type_device}' in '{intent_list.intents[0].room_name}'."
        else:
            return "Orchestrator: Could not find matching devices in configuration."

    # ------------------------------------------------------------------
    # Step 5 — Select target device(s) (Pydantic structured output)
    # ------------------------------------------------------------------
    emit("Orchestrator", "Selecting devices...")
    devices = _select_devices(user_message, merged_yaml_subset, intent_list, session_id=session_id)"""

code = code.replace(old_code, new_code)
with open("app/agent_system/orchestrator.py", "w") as f:
    f.write(code)

