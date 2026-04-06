"""
Orchestrator – Manager Agent

Routes user requests directly to the appropriate specialist agent:
  - home_control_agent for device control (turn on/off, set brightness, temperature, etc.)
  - home_monitor_agent for sensor readings (temperature, humidity, brightness, etc.)
"""

from smolagents import CodeAgent

from app.agent_system.model import model
from app.agent_system.agents.home_control_agent import home_control_agent
from app.agent_system.agents.home_monitor_agent import home_monitor_agent
from app.agent_system.tools import conversation_history_tool


# ---------------------------------------------------------------------------
# Manager Agent
# ---------------------------------------------------------------------------

_INSTRUCTIONS = """
    You are a smart home assistant orchestrator.

    ## Output format (STRICT)
    Every response you produce must contain exactly one code block:
    Thoughts: <your reasoning>
    ```python
    # code here
    ```

    ## ROUTING — Pick ONE agent, then final_answer()

    **A) Device control** (turn on/off, set brightness, colour temperature, thermostat temperature/mode):
    → Pass the user's message to home_control_agent.
    ```python
    answer = home_control_agent(task="<user message>")
    final_answer(answer)
    ```

    **B) Sensor / monitoring** (check temperature, humidity, brightness level, device state):
    → Pass the user's message to home_monitor_agent.
    ```python
    answer = home_monitor_agent(task="<user message>")
    final_answer(answer)
    ```

    **C) Anything else** (unknown, off-topic):
    ```python
    final_answer("Sorry, I can only help with controlling or monitoring smart home devices.")
    ```

    ## RULES
    - Call exactly ONE agent, then final_answer(). That's it — one step.
    - NEVER retry or call the same agent twice.
    - NEVER call both agents for the same request.

    ## Examples

    User: "turn on the living room light"
    ```python
    answer = home_control_agent(task="turn on the living room light")
    final_answer(answer)
    ```

    User: "set bedroom thermostat to 24 degrees"
    ```python
    answer = home_control_agent(task="set bedroom thermostat to 24 degrees")
    final_answer(answer)
    ```

    User: "what is the bedroom temperature?"
    ```python
    answer = home_monitor_agent(task="what is the bedroom temperature?")
    final_answer(answer)
    ```

    User: "check the living room light brightness"
    ```python
    answer = home_monitor_agent(task="check the living room light brightness")
    final_answer(answer)
    ```
"""

manager_agent = CodeAgent(
    tools=[],
    model=model,
    managed_agents=[
        home_control_agent,
        home_monitor_agent,
    ],
    max_steps=2,
    additional_authorized_imports=["time", "datetime"],
    verbosity_level=1,
    stream_outputs=True,
    code_block_tags="markdown",
    instructions=_INSTRUCTIONS,
)
