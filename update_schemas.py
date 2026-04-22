with open("app/agent_system/schemas.py", "r") as f:
    text = f.read()

import re
text = re.sub(
    r'class SensorAction\(BaseModel\):\n.*?class DeviceAction\(BaseModel\):',
    r'''class SensorAction(BaseModel):
    """One sensor function within a device, containing multiple attributes."""
    sensor_name: str
    shared_attributes: Dict[str, Any]

    def __init__(self, **data):
        if "shared_attribute" in data and "shared_attributes" not in data:
            data["shared_attributes"] = data.pop("shared_attribute")
        super().__init__(**data)

class DeviceAction(BaseModel):''',
    text,
    flags=re.DOTALL
)

with open("app/agent_system/schemas.py", "w") as f:
    f.write(text)
