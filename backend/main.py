import json

from dotenv import load_dotenv

load_dotenv()  # must be called before any agent import reads env vars

from agents.emergency_resource_agent import emergency_resource_agent
from agents.risk_region_agent import risk_region_agent

LAT = 44.63
LNG = -124.05

if __name__ == "__main__":
    # print("\n=== Flood Risk Analysis ===")
    
    # risk_result = risk_region_agent(LAT, LNG)
    # print(json.dumps(risk_result, indent=2))

    print("\n=== Emergency Resources ===")
    
    resource_result = emergency_resource_agent(LAT, LNG)
    print(json.dumps(resource_result, indent=2))
