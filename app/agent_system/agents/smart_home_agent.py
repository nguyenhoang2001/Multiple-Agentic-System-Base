"""
Managed Smart Home Agent

Equipped with:
  - SensorLogsTool       : fetches live sensor readings from the hub API.
  - SmartHomeControlTool : sends control commands to the hub API.

Both tools accept natural-language device references (e.g. "bedroom light")
and resolve them automatically via the device_resolver — no knowledge base
lookup is needed.

Handles two responsibilities:
  1. SENSOR READS    — reads live values (temperature, brightness, lock state, etc.)
  2. CONTROL COMMANDS — turns devices on/off, adjusts settings, etc.

Uses ToolCallingAgent (JSON format) for structured tool invocation.
"""

from smolagents import ToolCallingAgent

from app.agent_system.model import model
from app.agent_system.tools.smart_home_control_tool import smart_home_control_tool
from app.agent_system.tools.sensor_logs_tool import sensor_logs_tool


smart_home_agent = ToolCallingAgent(
    tools=[sensor_logs_tool, smart_home_control_tool],
    model=model,
    max_steps=2,
    verbosity_level=1,
    stream_outputs=True,
    name="smart_home_agent",
    description=(
        "Handles all smart home hub interactions. "
        "Use for: (1) SENSOR READS — current temperature, brightness, lock state, volume, CO2, humidity, etc. "
        "Accepts natural-language device references (e.g. 'bedroom light') and resolves them automatically. "
        "(2) CONTROL COMMANDS — turn lights on/off, adjust brightness, set thermostat, lock/unlock door, toggle plugs, move blinds, control speakers."
    ),
)
