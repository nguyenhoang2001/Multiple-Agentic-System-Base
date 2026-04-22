"""
Orchestrator – Deterministic IoT Pipeline

Replaces the previous CodeAgent master agent with a Python function that:
  1. Calls the LLM once with JSON structured output (Pydantic) to extract intent
  2. Checks Buffer Window Memory
  3. Delegates to clarification_agent if room/device info is missing
  4. Calls iterate_smart_home_yaml() deterministically to get the YAML subset
  5. Calls the LLM once with JSON structured output to select the target device(s)
  6. Delegates code generation + API execution to iot_action_agent (CodeAgent)

Why no CodeAgent for orchestration?
  Small local models (gemma4:e2b, qwen3:1.7b) hallucinate extra kwargs, write
  comments instead of code, and use `pass` instead of calling sub-agents when
  asked to orchestrate via code generation.  Structured JSON output is orders of
  magnitude more reliable for these models.

The ONLY CodeAgent in the pipeline is iot_action_agent — code generation is
appropriate there because it generates Python that calls CoreIoT tool functions.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from collections.abc import Callable
from typing import List, Optional

from app.agent_system.agents.clarification_agent import clarification_agent
from app.agent_system.agents.iot_action_agent import iot_action_agent
from app.agent_system.model import model, thinking_model
from app.agent_system.schemas import DeviceAction, DeviceActionList, UserIntent, UserIntentList
from app.agent_system.tools.buffer_window_tools import check_buffer_window_tool
from app.agent_system.memory.buffer_window import get_current_buffer
from app.vectore_store.conversation_memory import load_conversation_context
from app.agent_system.tools.yaml_iterator import (
    iterate_smart_home_yaml,
    list_available_rooms,
    get_room_and_device_types,
    get_device_summary,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ---------------------------------------------------------------------------
# System prompts for structured LLM calls
# ---------------------------------------------------------------------------

def _get_intent_system_prompt(session_id: str = None, user_message: str = "") -> str:
    device_summary = get_device_summary()
    buf = get_current_buffer()
    recent_context = buf.to_context_string(limit=5) if buf else ""
    conversation_history = load_conversation_context(user_message, session_id=session_id) if session_id else ""
    
    return f"""\
Extract intent as a JSON ARRAY of objects: [{{"room_name": "...", "type_device": "...", "device_name": "..."}}]. Use `null` if missing. Maps to "all" if user says "tất cả" or implicitly refers to multiple rooms/devices.
If there are multiple devices or rooms, output MULTIPLE objects in the array.
You MUST output ONLY a valid JSON array. No explanations, no conversation.
Available devices:
{device_summary}

If the user uses references like "hồi nãy", "thiết bị vừa rồi", "như trên", use the Recent Context and History to fill in the exact device_name and room_name.

Recent Context (last actions): {recent_context}
History: {conversation_history}

Examples:
"bật đèn phòng khách" → [{{"room_name": "living_room", "type_device": "smart_light_fan", "device_name": "Celling_fan_bedside_night_light"}}]
"vui lòng cho biết quạt ở phòng khách có bật không và bật đèn ngủ ở phòng ngủ" → [{{"room_name": "living_room", "type_device": "smart_light_fan", "device_name": "Celling_fan_bedside_night_light"}}, {{"room_name": "bedroom", "type_device": "smart_night_light", "device_name": "bedroom_night_light_controller"}}]
"tắt tất cả các thiết bị" → [{{"room_name": "all", "type_device": "all", "device_name": "all"}}]
"""

def _get_retriever_system_prompt() -> str:
    from app.agent_system.memory.buffer_window import get_current_buffer
    buf = get_current_buffer()
    recent_context = buf.to_context_string(limit=20) if buf else "(No recent context)"
    
    return f"""\
Select matching device(s) and ONLY the requested sensor(s) from YAML. You MUST output your answer EXACTLY matching this JSON format:
```json
{{
  "devices": [
    {{
      "name_device": "<name>",
      "token": "<token>",
      "device_id": "<id>",
      "room": "<room>",
      "type_device": "<type>",
      "sensors": [
        {{
          "sensor_name": "<sensor>",
          "shared_attributes": {{
            "<k>": <v>
          }}
        }}
      ]
    }}
  ]
}}
```

Rules:
1. ONLY include the specific `sensor_name` and `name_key` that match the user's request. DO NOT include all sensors if the user only asked for one.
2. `shared_attributes` MUST be ONE dict matching `name_key` directly to its value. DO NOT output nested dicts.
3. If changing state ("bật"/"tắt"/etc): `<v>` must be the primitive actual value (e.g., `true`, `false`, `1`, `0`).
4. If altering, modifying, or changing state ("đổi"/"change"/etc): `<v>` MUST BE the logical opposite of the CURRENT state (check `Recent Context` for current state), or pick a DIFFERENT valid integer/enum value. DO NOT set to `null` if the user wants to change a value.
5. If checking/reading state ("read"/"kiểm tra"/"trạng thái"/etc): EVERY `<v>` MUST BE LITERALLY `null`. NEVER hallucinate a value when reading. (e.g. `"led_celling": null`).
6. Copy token and device_id EXACTLY from YAML. NEVER invent.

Recent Context (Buffer):
{recent_context}

Example Read Request: "kiểm tra đèn"
Output:
```json
{{
  "devices": [
    {{
      "name_device": "living_room_ceiling_light_fan",
      "token": "xdF2nW...",
      "device_id": "fcce...",
      "room": "living_room",
      "type_device": "smart_light_fan",
      "sensors": [
        {{
          "sensor_name": "led_celling",
          "shared_attributes": {{
            "led_celling": null
          }}
        }}
      ]
    }}
  ]
}}
```
"""


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------


def _parse_json(text: str) -> any:
    """Extract and parse the first JSON object or array from a model response.

    Handles plain JSON, markdown code blocks (```json ... ``` or ``` ... ```),
    and any surrounding text the model may add.
    """
    if not text:
        raise ValueError("Empty response from model")
    # Strip markdown code fences
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        text = fence.group(1)
    # Find first { or [ and parse from there
    match = re.search(r"[{\[]", text)
    if match:
        text = text[match.start():]
        
    # Auto-close brackets to handle truncated generation (e.g., max_new_tokens hit)
    stack = []
    in_string = False
    escape = False
    for char in text:
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                stack.append('}')
            elif char == '[':
                stack.append(']')
            elif char == '}' or char == ']':
                if stack and stack[-1] == char:
                    stack.pop()
                    
    if in_string:
        text += '"'
    while stack:
        text += stack.pop()
        
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Nhờ ast (Abstract Syntax Tree) để parse json xài nháy đơn (dict của Python)
        return ast.literal_eval(text)


def _extract_intent(
    user_message: str,
    session_id: str,
    history: Optional[list] = None,
) -> UserIntentList:
    """Call the LLM to extract room + device type from the user message.

    History (last few turns) is prepended so follow-up messages like
    "phòng khách" are correctly resolved in context.
    """
    def _text(text: str) -> list:
        return [{"type": "text", "text": text}]

    messages: list = [{"role": "system", "content": _text(_get_intent_system_prompt(session_id, user_message))}]

    # Combine history into the user message to prevent the model from roleplaying as "assistant"
    # and falling into conversational output instead of JSON.
    user_req = ""
    if history:
        user_req += "[Recent Conversation History]\n"
        for msg in history[-4:]:  # last 2 turns
            user_req += f"{msg['role'].upper()}: {msg['content']}\n"
        user_req += "\n"
        
    user_req += f"[Current Request]\nUSER: {user_message}\n\n=> Output JSON intent now:"

    messages.append({"role": "user", "content": _text(user_req)})

    try:
        logger.info(f"API CALL: _extract_intent")
        logger.info(f"PROMPT messages for _extract_intent:\n{json.dumps(messages, ensure_ascii=False, indent=2)}")
        response = thinking_model(messages=messages)
        logger.info(f"AI RESPONSE: _extract_intent: {response.content}")
        data = _parse_json(response.content)
        
        if isinstance(data, dict):
            data = [data]
            
        intents = []
        for item in data:
            if isinstance(item, dict):
                intents.append(UserIntent(
                    room_name=item.get("room_name") or None,
                    type_device=item.get("type_device") or None,
                    device_name=item.get("device_name") or None,
                ))
        if not intents:
            intents.append(UserIntent())
            
        return UserIntentList(intents=intents)
    except Exception as e:
        logger.warning(f"Intent extraction failed: {str(e)} — returning empty intent")
        return UserIntentList(intents=[UserIntent()])


def _select_devices(user_message: str, yaml_subset: str, intent_list: UserIntentList = None, session_id: str = None) -> List[DeviceAction]:
    """Call the LLM to select device(s) from the YAML subset and determine
    what value to set (or None for read).

    Returns a validated list of DeviceAction objects.
    """
    conversation_history = load_conversation_context(user_message, session_id=session_id) if session_id else "(empty history)"
    
    def _text(text: str) -> list:
        return [{"type": "text", "text": text}]

    intent_yaml = ""
    if intent_list and intent_list.intents:
        intent_yaml = "Extracted Intent (YAML):\nrooms:\n"
        for i in intent_list.intents:
            intent_yaml += f"  - name: {i.room_name}\n"
            intent_yaml += f"    type_device:\n"
            intent_yaml += f"      - name_type: {i.type_device}\n"
            intent_yaml += f"        devices:\n"
            intent_yaml += f"          - name: {i.device_name}\n"
        intent_yaml += "\n\n"


    try:
        logger.info("API CALL: _select_devices")
        sys_prompt = _get_retriever_system_prompt()
        messages = [
            {"role": "system", "content": _text(sys_prompt)},
            {
                "role": "user",
                "content": _text(
                    f"User request: {user_message}\n\n{intent_yaml}Device YAML:\n{yaml_subset}\n\nLong-term Conversation History:\n{conversation_history}"
                ),
            },
        ]
        logger.info(f"PROMPT messages for _select_devices:\n{json.dumps(messages, ensure_ascii=False, indent=2)}")
        response = thinking_model(messages=messages)
        logger.info(f"AI RESPONSE: _select_devices: {response.content}")
        data = _parse_json(response.content)

        # Normalise: model may return {"devices": [...]} or bare [...]
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict) and "devices" in data:
            raw_list = data["devices"]
        else:
            raw_list = [data]

        return DeviceActionList(devices=raw_list).devices

    except Exception as e:
        logger.warning(f"Device selection failed: {str(e)}")
        return []


def _generate_final_response(user_message: str, result: str, yaml_subset: str = "") -> str:
    """Sử dụng LLM để chuyển đổi kết quả thực thi thành câu trả lời ngôn ngữ tự nhiên."""
    def _text(text: str) -> list:
        return [{"type": "text", "text": text}]
        
    system_prompt = (
        "Act as a smart home assistant. Write a short, natural response based on 'User Request' & 'System Result'. "
        "Explain errors sympathetically if any. Map the attributes in 'System Result' to their 'sensor_name' using 'Device Configuration' and READ THE DESCRIPTION OF ATTRIBUTE OF EACH SENSOR to summarize the status BY SENSOR NAME. Output final answer only."
    )
    
    try:
        logger.info("API CALL: _generate_final_response")
        messages = [
            {"role": "system", "content": _text(system_prompt)},
            {
                "role": "user",
                "content": _text(
                    f"User Request: {user_message}\n\nSystem Result:\n{result}\n\nDevice Configuration:\n{yaml_subset}"
                ),
            },
        ]
        logger.info(f"PROMPT messages for _generate_final_response:\n{json.dumps(messages, ensure_ascii=False, indent=2)}")
        response = thinking_model(messages=messages)
        logger.info(f"AI RESPONSE: _generate_final_response: {response.content}")
        return response.content
    except Exception as e:
        logger.warning(f"Final response generation failed: {str(e)}")
        return f"System reported result:\n{result}"


# ---------------------------------------------------------------------------
# Public pipeline entry point
# ---------------------------------------------------------------------------


def run_iot_pipeline(
    user_message: str,
    session_id: str,
    history: Optional[list] = None,
    on_step: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Deterministic IoT orchestration pipeline.

    Args:
        user_message: The latest user message.
        history:      Prior turns as [{"role": "user"|"assistant", "content": str}].
                      Used to provide context for follow-up messages.
        on_step:      Optional callback for streaming step-level status updates.

    Returns:
        The final answer string to send back to the user.
    """

    def emit(agent_name: str, text: str) -> None:
        if on_step:
            on_step(f"{agent_name}: {text}\n\n")

    # ------------------------------------------------------------------
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
            merged_yaml_subset += subset + "\n"
            
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
    devices = _select_devices(user_message, merged_yaml_subset, intent_list, session_id=session_id)

    if not devices:
        return "Orchestrator: Could not determine target device."

    devices_json = json.dumps(
        [d.model_dump() for d in devices], ensure_ascii=False
    )
    logger.info("Selected devices: %s", devices_json)

    # ------------------------------------------------------------------
    # Step 6 — Route & execute via iot_action_agent (CodeAgent)
    # Decides write vs read split, calls post/read tools, updates BufferWindow
    # ------------------------------------------------------------------
    emit("Orchestrator", "Executing command...")
    raw_result = iot_action_agent.run(devices_json)
    
    emit("Orchestrator", "Generating response...")
    final_response = _generate_final_response(user_message, raw_result, merged_yaml_subset)
    
    # Optional prefixes like "IoT_Action_Agent: " may not be needed anymore
    return final_response
