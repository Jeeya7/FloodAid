import json

from agents.risk_region_agent import risk_region_agent

state = {
    "map_bounds": {
        "south": 44.55,
        "north": 44.75,
        "west": -124.10,
        "east": -123.80,
    },
    "debug_steps": [],
}

if __name__ == "__main__":
    final = risk_region_agent(state)
    print(json.dumps(final, indent=2))
