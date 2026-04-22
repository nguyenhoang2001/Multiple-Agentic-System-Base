text = '{"devices": [{"name_device": "Celling_fan_bedside_night_light", "token": "xdF2nW4aR9SAdqqPiym0", "device_id": "fcceeaa0-3111-11f1-9981-cffbb69f5b14", "room": "living_room", "type_device": "smart_light_fan", "sensors": [{"sensor_name": "led_celling", "shared_attributes": {"led_celling": null}}, {"sensor_name": "brightness_beside_night_light", "shared_attributes": {"led_beside_night_light": null, "brightness_beside_night_light": null}}, {"sensor_name": "fan", "shared_attributes": {"integer_fan_speed": null}}}]}'

def parse_with_stack(t):
    stack = []
    for i, c in enumerate(t):
        if c in '{[': stack.append(c)
        elif c in '}]':
            if not stack:
                print(f"Error at {i}: stack empty, char {c}")
                return
            last = stack.pop()
            if (c == '}' and last != '{') or (c == ']' and last != '['):
                print(f"Mismatch at {i}: expected {']' if last=='[' else '}'} got {c}")
                return
    print("Parsed correctly up to length", len(t), "remaining stack:", stack)

parse_with_stack(text)
