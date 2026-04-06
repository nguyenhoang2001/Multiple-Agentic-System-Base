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
Call `sensor_logs_reader` with the device_id and sensor_type you extracted from Step 1.

Example:
```python
result = sensor_logs_reader(device_id="thermostat_01", sensor_type="temperature")
final_answer(result)
```

## RULES
- NEVER skip Step 1. Always look up first, then query.
- NEVER guess or invent a device_id. Only use IDs found in the retrieved documents.
- The `retriever` tool returns a string, NOT a tuple. Do NOT try to unpack it.
- final_answer() accepts exactly ONE string argument. Combine all results into a single string before calling it.
- Pass None for sensor_type if the user wants all readings from a device.
- Pass None for device_id if the user wants readings from all devices.
- NEVER retry or reattempt a tool call. If a tool returns an error or unexpected result, return that result via final_answer() immediately.
- You have exactly 2 steps: Step 1 (retriever) and Step 2 (sensor_logs_reader + final_answer). Do NOT add extra steps.
"""


home_monitor_agent = CodeAgent(
    tools=[doc_retriever_tool, sensor_logs_tool],
    model=model,
    max_steps=3,
    verbosity_level=1,
    stream_outputs=True,
    name="home_monitor_agent",
    description=(
        "Reads live sensor data and device states from smart home devices. "
        "Use for: current temperature, brightness level, humidity, "
        "thermostat setpoint and mode. "
        "First looks up the correct device_id and sensor_type from the "
        "knowledge base using the retriever tool, then queries the sensor data. "
        "Returns 'not found' if no matching device or sensor exists."
    ),
    code_block_tags="markdown",
    instructions=_INSTRUCTIONS,
)
