import json
from pathlib import Path
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel, Field
from agents.risk_region_agent import risk_region_agent
from agents.emergency_resource_agent import emergency_resource_agent
from agents.chat import chat

router = APIRouter()

# figure out where to save agent responses
AGENT_RESPONSE_DIR = Path(__file__).resolve().parent.parent / "agent_response"
AGENT_RESPONSE_DIR.mkdir(exist_ok=True)  


# this defines what the frontend has to send for location-based requests
class LocationRequest(BaseModel):
    lat: float
    lng: float
    radius_miles: float = Field(default=25, gt=0)  # defaults to 25 miles, must be > 0


# this defines what the frontend sends for chat messages
class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []  # conversation history, empty by default


# simple health check so we can verify the backend is running
@router.get("/health")
def health_check():
    return {"status": "backend running"}


# reads the last saved risk analysis and returns the worst region
# the frontend uses this to show an alert banner without re-running the AI pipeline
@router.get("/alert")
def get_alert():
    try:
        # load the cached risk data we saved last time
        data = json.loads((AGENT_RESPONSE_DIR / "risk_region_agent.json").read_text())
        regions = data.get("regions", [])

        # rank risk levels so we can find the worst one
        order = ["low", "moderate", "high", "critical"]
        top = max(regions, key=lambda r: order.index(r.get("risk_level", "low")), default=None)

        if top:
            return {
                "alert": f"Flood risk {top['risk_level']} near {top['name'].title()}",
                "risk_level": top["risk_level"],
            }
    except Exception:
        # if the file doesn't exist yet or is broken, just return no alert
        pass

    return {"alert": "No active flood alerts", "risk_level": "low"}


# main flood risk endpoint — takes user location, runs the full AI pipeline

@router.post("/risk-regions")
async def get_risk_regions(body: LocationRequest):
    result = risk_region_agent(
        lat=body.lat,
        lng=body.lng,
        radius_miles=body.radius_miles,
    )
    # save the result to disk so the chat agent and alert endpoint can read it later
    (AGENT_RESPONSE_DIR / "risk_region_agent.json").write_text(json.dumps(result))
    return result


# resource finder endpoint — takes user location, finds hospitals/food/shelters nearby
@router.post("/resources")
async def get_resources(body: LocationRequest):
    result = emergency_resource_agent(
        lat=body.lat,
        lng=body.lng,
    )
    # save to disk so Droppy can reference it when answering chat questions
    (AGENT_RESPONSE_DIR / "emergency_resource_agent.json").write_text(json.dumps(result))
    return result


# chat endpoint — takes a message and conversation history, returns Droppy's response
# Droppy reads the saved risk and resource files above to give location-specific answers
@router.post("/chat")
async def get_chat(req: ChatRequest):
    result = chat(
        req.message,
        req.history,
    )
    return result