import json

from dotenv import load_dotenv

load_dotenv()  # must be called before any agent import reads env vars

from agents.emergency_resource_agent import emergency_resource_agent
from agents.risk_region_agent import risk_region_agent

if __name__ == "__main__":
    print("\n=== Flood Risk Analysis ===")
    
    risk_result = risk_region_agent(44.63, -124.05)
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
