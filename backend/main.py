import json

from dotenv import load_dotenv

load_dotenv()  # must run before any agent import reads env vars

from agents.emergency_resource_agent import emergency_resource_agent
from agents.risk_region_agent import risk_region_agent

if __name__ == "__main__":
    print("\n=== Flood Risk Analysis ===")
    risk_state = {
        "map_bounds": {
            "south": 44.55,
            "north": 44.75,
            "west": -124.10,
            "east": -123.80,
        },
        "debug_steps": [],
    }
    risk_result = risk_region_agent(risk_state)
    print(json.dumps(risk_result, indent=2))

    print("\n=== Emergency Resources ===")
    resource_state = {
        "user_location": {
            "lat": 44.63,
            "lng": -124.05,
        },
        "lat": 44.63,
        "lng": -124.05,
        "radius_miles": 10,
        "debug_steps": [],
    }
    resource_result = emergency_resource_agent(resource_state)
    print(json.dumps(resource_result, indent=2))
