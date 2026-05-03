import json
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agents.risk_region_agent import risk_region_agent
from chat import router as chat_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

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