const fs = require('fs');

// Update schemas.py
let schemas = fs.readFileSync('app/agent_system/schemas.py', 'utf8');

const oldIntent = `class UserIntent(BaseModel):
    """
    Structured output from the Master Agent's intent extraction step.

    The LLM is asked to extract room_name and type_device from the user's
    natural-language message. Both fields are Optional — None signals that
    the information was not present in the message and further clarification
    is needed.
    """

    room_name: Optional[str] = Field(
        default=None,
        description=(
            "The room name in snake_case English, e.g. 'living_room', 'kitchen', 'bedroom'. None if the user did not mention a room."
        ),
    )
    type_device: Optional[str] = Field(
        default=None,
        description=(
            "The device category, e.g. 'smart_light' or 'smart_fan'. "
            "None if the user did not mention a device type."
        ),
    )`;

const newIntent = `from typing import Union

class UserIntent(BaseModel):
    """
    Structured output from the Master Agent's intent extraction step.
    """

    room_name: Union[str, List[str], None] = Field(
        default=None,
        description=(
            "The room name(s) in snake_case English, e.g. 'living_room', ['living_room', 'kitchen'], "
            "or 'all' for all rooms. None if the user did not mention a room at all."
        ),
    )
    type_device: Union[str, List[str], None] = Field(
        default=None,
        description=(
            "The device category(s), e.g. 'smart_light', 'smart_fan', or 'all' for all devices. "
            "None if the user did not mention a device type."
        ),
    )`;

schemas = schemas.replace(oldIntent, newIntent);
fs.writeFileSync('app/agent_system/schemas.py', schemas);

// Update orchestrator.py
let orchestrator = fs.readFileSync('app/agent_system/orchestrator.py', 'utf8');

const oldPrompt = `Room mappings:
  phòng khách                → "living_room"
  bếp / nhà bếp / phòng bếp → "kitchen"
  phòng ngủ                  → "bedroom"
  tất cả phòng / các phòng   → "all"
  not mentioned              → null

Device type mappings:
  đèn / bóng đèn / đèn trần / đèn ngủ / đèn bếp → "smart_light"
  quạt / quạt trần                                → "smart_fan"
  tất cả thiết bị / các thiết bị / mọi thứ       → "all"
  not mentioned                                   → null

Examples:
  "bật đèn trần phòng khách" → {"room_name": "living_room", "type_device": "smart_light"}
  "tắt quạt bếp"             → {"room_name": "kitchen",     "type_device": "smart_fan"}
  "bật tất cả thiết bị bếp"  → {"room_name": "kitchen",     "type_device": "all"}
  "tắt hết mọi thiết bị"     → {"room_name": "all",         "type_device": "all"}
  "bật đèn"                  → {"room_name": null,          "type_device": "smart_light"}
  "phòng khách"              → {"room_name": "living_room", "type_device": null}`;

const newPrompt = `Room mappings:
  phòng khách                → "living_room"
  bếp / nhà bếp / phòng bếp → "kitchen"
  phòng ngủ                  → "bedroom"
  tất cả phòng / các phòng   → "all"
  2 phòng trở lên            → ["living_room", "kitchen", ...]
  not mentioned              → null

Device type mappings:
  đèn / bóng đèn / đèn trần / đèn ngủ / đèn bếp → "smart_light"
  quạt / quạt trần                                → "smart_fan"
  tất cả thiết bị / các thiết bị / mọi thứ       → "all"
  not mentioned                                   → null

Examples:
  "bật đèn trần phòng khách" → {"room_name": "living_room", "type_device": "smart_light"}
  "tắt quạt bếp"             → {"room_name": "kitchen",     "type_device": "smart_fan"}
  "bật tất cả thiết bị bếp"  → {"room_name": "kitchen",     "type_device": "all"}
  "tắt hết mọi thiết bị"     → {"room_name": "all",         "type_device": "all"}
  "bật đèn"                  → {"room_name": null,          "type_device": "smart_light"}
  "bật tất cả đèn"           → {"room_name": "all",         "type_device": "smart_light"}
  "tất cả thiết bị ở phòng khách và bếp"         → {"room_name": ["living_room", "kitchen"], "type_device": "all"}
  "cả nhà"                   → {"room_name": "all",         "type_device": "all"}
  "phòng khách"              → {"room_name": "living_room", "type_device": null}`;

orchestrator = orchestrator.replace(oldPrompt, newPrompt);

fs.writeFileSync('app/agent_system/orchestrator.py', orchestrator);

console.log("Patched Intent and Prompts!");
