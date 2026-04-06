"""
Home Control Agent — executes device commands.

Uses a two-step workflow:
  1. Calls doc_retriever_tool (retriever) to look up the correct device_id,
     action, and parameters from the IoT knowledge base.
  2. Sends the resolved command via smart_home_control_tool.

If no matching device or action is found in the knowledge base, the agent
returns a "not found" message instead of guessing.
"""

from smolagents import CodeAgent

from app.agent_system.model import model
from app.agent_system.tools.retriever_tools import doc_retriever_tool
from app.agent_system.tools.smart_home_control_tool import smart_home_control_tool


_INSTRUCTIONS = """\
You control smart home devices using a TWO-STEP process. Follow these steps IN ORDER:

## STEP 1 — Look up the devices (ALWAYS do this first)
Call the `retriever` tool with a query describing what the user wants.
The retriever returns a TEXT string containing knowledge base documents.

Example:
```python
docs = retriever(query="turn on living room light device_id action parameters")
print(docs)
```

Read the printed text carefully and extract ALL matching devices:
  - device_id  (e.g. "light_living_01", "thermostat_01")
  - action     (e.g. "turn_on", "turn_off", "set", "set_temperature")
  - parameters (e.g. {"brightness": 80}, {"setpoint": 22, "mode": "heat"}, or None)

If the retrieved text does NOT contain a matching device or a suitable action
for the user's request, return:
```python
final_answer("Sorry, I could not find an appropriate device or command for your request.")
```

## STEP 2 — Send the commands
Call `smart_home_control` for EACH device that matches the user's request.
Collect all results, then call final_answer() once with a summary.

### Single device example:
```python
result = smart_home_control(device_id="light_living_01", action="turn_on", parameters={"brightness": 80})
final_answer(result)
```

### Multiple devices example (e.g. "turn all lights off"):
```python
result1 = smart_home_control(device_id="light_living_01", action="turn_off", parameters=None)
result2 = smart_home_control(device_id="light_bedroom_01", action="turn_off", parameters=None)
final_answer(f"Living room light: {result1}\\nBedroom light: {result2}")
```

## RULES
- NEVER skip Step 1. Always look up first, then control.
- NEVER guess or invent a device_id. Only use IDs found in the retrieved documents.
- The `retriever` tool returns a string, NOT a tuple. Do NOT try to unpack it.
- Always include all three fields when calling smart_home_control: device_id, action, parameters.
- final_answer() accepts exactly ONE string argument. Combine all results into a single string before calling it.
- If the user says "all lights" or "all devices", send a command to EACH matching device.
- If the user says "lowest" / "minimum", use value 1. If "highest" / "maximum", use value 100.
- If no brightness is specified for lights, use default 80.
- NEVER retry or reattempt a tool call. If a tool returns an error or unexpected result, include that error in the final_answer() immediately.
- You have exactly 2 steps: Step 1 (retriever) and Step 2 (all smart_home_control calls + final_answer). Call ALL devices in the SAME step.
"""

home_control_agent = CodeAgent(
    tools=[doc_retriever_tool, smart_home_control_tool],
    model=model,
    max_steps=4,
    verbosity_level=1,
    stream_outputs=True,
    name="home_control_agent",
    description=(
        "Executes control commands on one or more smart home devices. "
        "Use for: turn lights on/off, adjust brightness or colour temperature, "
        "set thermostat temperature or mode. Supports multi-device commands like "
        "'turn all lights off'. "
        "First looks up the correct device_id, action, and parameters from the "
        "knowledge base using the retriever tool, then sends the command to each device. "
        "Returns 'not found' if no matching device or action exists."
    ),
    code_block_tags="markdown",
    instructions=_INSTRUCTIONS,
)
