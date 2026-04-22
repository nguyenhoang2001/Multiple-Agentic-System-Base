from app.agent_system.orchestrator import _extract_intent
import json

intent = _extract_intent("bật tất cả thiết bị ở phòng khách")
print("Extracted:", intent.model_dump())
