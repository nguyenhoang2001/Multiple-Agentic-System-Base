from app.agent_system.tools.yaml_iterator import iterate_smart_home_yaml

print(iterate_smart_home_yaml(room_name=["living_room", "kitchen"], type_device="all"))
