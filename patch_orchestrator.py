import re

with open("app/agent_system/orchestrator.py", "r") as f:
    code = f.read()

# Patch _select_devices definition
code = code.replace(
    "def _select_devices(user_message: str, yaml_subset: str, intent: UserIntent = None, session_id: str = None)",
    "def _select_devices(user_message: str, yaml_subset: str, intent_list: UserIntentList = None, session_id: str = None)"
)

intent_yaml_old = """    intent_yaml = ""
    if intent:
        intent_yaml = (
            "Extracted Intent (YAML):\\n"
            "rooms:\\n"
            f"  - name: {intent.room_name}\\n"
            "    type_device:\\n"
            f"      - name_type: {intent.type_device}\\n"
            "        devices:\\n"
            f"          - name: {intent.device_name}\\n\\n"
        )"""

intent_yaml_new = """    intent_yaml = ""
    if intent_list and intent_list.intents:
        intent_yaml = "Extracted Intent (YAML):\\nrooms:\\n"
        for i in intent_list.intents:
            intent_yaml += f"  - name: {i.room_name}\\n"
            intent_yaml += f"    type_device:\\n"
            intent_yaml += f"      - name_type: {i.type_device}\\n"
            intent_yaml += f"        devices:\\n"
            intent_yaml += f"          - name: {i.device_name}\\n"
        intent_yaml += "\\n\\n"
"""

code = code.replace(intent_yaml_old, intent_yaml_new)

with open("app/agent_system/orchestrator.py", "w") as f:
    f.write(code)

