import json

def _fix_truncated_json(text: str) -> str:
    stack = []
    in_string = False
    escape = False
    
    for char in text:
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                stack.append('}')
            elif char == '[':
                stack.append(']')
            elif char == '}' or char == ']':
                if stack and stack[-1] == char:
                    stack.pop()
                else:
                    # Mismatched parsing or we started mid-way, just ignore.
                    pass
                    
    if in_string:
        text += '"'
        
    while stack:
        text += stack.pop()
        
    return text

text = '{"devices": [{"name_device": "Celling_fan_bedside_night_light", "token": "xdF2nW4aR9SAdqqPiym0", "device_id": "fcceeaa0-3111-11f1-9981-cffbb69f5b14", "room": "living_room", "type_device": "smart_light_fan", "sensors": [{"sensor_name": "led_celling", "shared_attributes": {"led_celling": null}}, {"sensor_name": "brightness_beside_night_light", "shared_attributes": {"led_beside_night_light": null, "brightness_beside_night_light": null}}, {"sensor_name": "fan", "shared_attributes": {"integer_fan_speed": null}}}]}'
fixed = _fix_truncated_json(text)
print("Fixed:", fixed)
try:
    print(json.loads(fixed))
except Exception as e:
    print("Error:", e)
