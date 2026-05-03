from fastapi import APIRouter
from pydantic import BaseModel, Field

from agents.risk_region_agent import risk_region_agent
from agents.emergency_resource_agent import emergency_resource_agent

router = APIRouter()


class LocationRequest(BaseModel):
    lat: float
    lng: float
    radius_miles: float = Field(default=25, gt=0)


@router.get("/health")
def health_check():
    return {"status": "backend running"}


@router.post("/risk-regions")
async def get_risk_regions(body: LocationRequest):
    """
    Uses lat/lng to determine bounding box or nearby regions.
    """
    result = risk_region_agent(
        lat=body.lat,
        lng=body.lng,
        radius_miles=body.radius_miles,
    )
    return result


@router.post("/resources")
async def get_resources(body: LocationRequest):
    result = emergency_resource_agent(
        lat=body.lat,
        lng=body.lng,
        radius_miles=body.radius_miles,
    )
    return result