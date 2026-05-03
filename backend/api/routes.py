import json
from pathlib import Path
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agents.risk_region_agent import risk_region_agent
from agents.emergency_resource_agent import emergency_resource_agent
from agents.chat import chat

router = APIRouter()

AGENT_RESPONSE_DIR = Path(__file__).resolve().parent.parent / "agent_response"
AGENT_RESPONSE_DIR.mkdir(exist_ok=True)


class LocationRequest(BaseModel):
    lat: float
    lng: float
    radius_miles: float = Field(default=25, gt=0)


class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []


@router.get("/health")
def health_check():
    return {"status": "backend running"}


@router.get("/alert")
def get_alert():
    try:
        data = json.loads((AGENT_RESPONSE_DIR / "risk_region_agent.json").read_text())
        regions = data.get("regions", [])
        order = ["low", "moderate", "high", "critical"]
        top = max(regions, key=lambda r: order.index(r.get("risk_level", "low")), default=None)
        if top:
            return {
                "alert": f"Flood risk {top['risk_level']} near {top['name'].title()}",
                "risk_level": top["risk_level"],
            }
    except Exception:
        pass
    return {"alert": "No active flood alerts", "risk_level": "low"}


@router.post("/risk-regions")
async def get_risk_regions(body: LocationRequest):
    result = risk_region_agent(
        lat=body.lat,
        lng=body.lng,
        radius_miles=body.radius_miles,
    )
    (AGENT_RESPONSE_DIR / "risk_region_agent.json").write_text(json.dumps(result))
    return result


@router.post("/resources")
async def get_resources(body: LocationRequest):
    result = emergency_resource_agent(
        lat=body.lat,
        lng=body.lng,
    )
    (AGENT_RESPONSE_DIR / "emergency_resource_agent.json").write_text(json.dumps(result))
    return result


@router.post("/chat")
async def get_chat(req: ChatRequest):
    result = chat(
        req.message,
        req.history,
    )
    return result