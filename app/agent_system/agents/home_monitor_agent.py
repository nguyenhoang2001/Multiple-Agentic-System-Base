"""
Home Monitor Agent — reads device sensor values and states.

Uses a two-step workflow:
  1. Calls doc_retriever_tool (retriever) to look up the correct device_id
     and sensor_type from the IoT knowledge base.
  2. Queries sensor data via sensor_logs_reader tool.

If no matching device or sensor type is found in the knowledge base, the agent
returns a "not found" message instead of guessing.
"""

from smolagents import CodeAgent

from app.agent_system.model import model
from app.agent_system.tools.retriever_tools import doc_retriever_tool
from app.agent_system.tools.sensor_logs_tool import sensor_logs_tool


_INSTRUCTIONS = """\
You read sensor data from smart home devices using a TWO-STEP process. Follow these steps IN ORDER:

## STEP 1 — Look up the device (ALWAYS do this first)
Call the `retriever` tool with a query describing the device and sensor the user wants.
The retriever returns a TEXT string containing knowledge base documents.

Example:
```python
docs = retriever(query="bedroom thermostat temperature device_id sensor_type")
print(docs)
```

Read the printed text carefully and extract:
  - device_id   (e.g. "thermostat_01", "light_living_01")
  - sensor_type (e.g. "temperature", "humidity", "brightness", "temperature_setpoint")

If the retrieved text does NOT contain a matching device or sensor type
for the user's request, return:
```python
final_answer("Sorry, I could not find an appropriate device or sensor for your request.")
```

## STEP 2 — Query the sensor data
Call `sensor_logs_reader` for EACH device that matches the user's request.
Collect all results, then call final_answer() once with a summary.

### Single device example:
```python
result = sensor_logs_reader(device_id="thermostat_01", sensor_type="temperature")
final_answer(result)
```

### Multiple devices example (e.g. "check all device temperatures"):
```python
result1 = sensor_logs_reader(device_id="thermostat_01", sensor_type="temperature")
result2 = sensor_logs_reader(device_id="light_living_01", sensor_type="brightness")
final_answer(f"Thermostat: {result1}\nLiving room light: {result2}")
```

## RULES
- NEVER skip Step 1. Always look up first, then query.
- NEVER guess or invent a device_id. Only use IDs found in the retrieved documents.
- The `retriever` tool returns a string, NOT a tuple. Do NOT try to unpack it.
- final_answer() accepts exactly ONE string argument. Combine all results into a single string before calling it.
- If the user says "all devices" or mentions multiple devices, query EACH matching device.
- Pass None for sensor_type if the user wants all readings from a device.
- Pass None for device_id if the user wants readings from all devices.
- NEVER retry or reattempt a tool call. If a tool returns an error or unexpected result, include that error in the final_answer() immediately.
- You have exactly 2 steps: Step 1 (retriever) and Step 2 (all sensor_logs_reader calls + final_answer). Call ALL devices in the SAME step.
"""


home_monitor_agent = CodeAgent(
    tools=[doc_retriever_tool, sensor_logs_tool],
    model=model,
    max_steps=4,
    verbosity_level=1,
    stream_outputs=True,
    name="home_monitor_agent",
    description=(
        "Reads live sensor data and device states from one or more smart home devices. "
        "Use for: current temperature, brightness level, humidity, "
        "thermostat setpoint and mode. Supports multi-device queries like "
        "'check all device temperatures'. "
        "First looks up the correct device_id and sensor_type from the "
        "knowledge base using the retriever tool, then queries sensor data for each device. "
        "Returns 'not found' if no matching device or sensor exists."
    ),
    code_block_tags="markdown",
    instructions=_INSTRUCTIONS,
)
