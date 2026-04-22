import json
text = '{"devices": [{"name_device": "Celling_fan_bedside_night_light", "token": "xdF2nW4aR9SAdqqPiym0", "device_id": "fcceeaa0-3111-11f1-9981-cffbb69f5b14", "room": "living_room", "type_device": "smart_light_fan", "sensors": [{"sensor_name": "led_celling", "shared_attributes": {"led_celling": null}}, {"sensor_name": "brightness_beside_night_light", "shared_attributes": {"led_beside_night_light": null, "brightness_beside_night_light": null}}, {"sensor_name": "fan", "shared_attributes": {"integer_fan_speed": null}}}]}]}'
try:
    json.loads(text)
except json.JSONDecodeError as e:
    print(f"Error at char {e.pos}:")
    start = max(0, e.pos - 20)
    end = min(len(text), e.pos + 20)
    print(text[start:end])
    print(" " * (e.pos - start) + "^")
