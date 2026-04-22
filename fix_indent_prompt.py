import re

with open("app/agent_system/orchestrator.py", "r") as f:
    code = f.read()

# Fix indentation and syntax from string replacement
code = code.replace("sys_prompt = _get_retriever_system_prompt()", "        sys_prompt = _get_retriever_system_prompt()")

with open("app/agent_system/orchestrator.py", "w") as f:
    f.write(code)

