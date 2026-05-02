import json

from agents.risk_region_agent import risk_region_agent

state = {"map_bounds": {}, "debug_steps": []}

if __name__ == "__main__":
    final = risk_region_agent(state)
    print(json.dumps(final, indent=2))
