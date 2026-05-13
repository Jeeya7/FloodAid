# tools/resource_tools.py
#
# LangChain @tool-decorated wrappers around the emergency resource services.
# Follows the same pattern as tools/risk_region_tools.py.
#
# Rules:
#   - Tools only fetch and return normalised data.
#   - Tools do NOT score, rank, or make routing decisions.
#   - All real logic lives in the services they call.

from typing import Any

from langchain_core.tools import tool

# import the actual service functions — tools are just thin wrappers around these
from services.food_service     import get_food_resources as _get_food_resources
from services.hospital_service import get_hospitals      as _get_hospitals
from services.shelter_service  import get_shelters       as _get_shelters


# ── Individual resource tools ─────────────────────────────────────────────────
# each tool wraps one service — the @tool decorator makes them callable by LangChain agents

@tool
def get_food_resources_tool(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Return food-assistance resources (food banks, meal sites, pantries) near a location.
    lat and lng are required (WGS-84 decimal degrees).
    radius_miles controls the search radius; defaults to 10.
    """
    if lat is None or lng is None:
        return {"source": "error", "resources": [], "error": "lat and lng are required."}

    # default to 10 miles if an invalid radius was passed
    radius = radius_miles if radius_miles and radius_miles > 0 else 10

    try:
        return _get_food_resources(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        # catch any unexpected errors so the agent pipeline doesn't crash
        return {"source": "error", "resources": [], "error": str(exc)}


@tool
def get_hospitals_tool(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Return hospital and medical resources (hospitals, urgent care, clinics) near a location.
    lat and lng are required (WGS-84 decimal degrees).
    radius_miles controls the search radius; defaults to 10.
    """
    if lat is None or lng is None:
        return {"source": "error", "resources": [], "error": "lat and lng are required."}

    radius = radius_miles if radius_miles and radius_miles > 0 else 10

    try:
        return _get_hospitals(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        return {"source": "error", "resources": [], "error": str(exc)}


@tool
def get_shelters_tool(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Return emergency shelter resources (evacuation shelters, warming centers) near a location.
    lat and lng are required (WGS-84 decimal degrees).
    radius_miles controls the search radius; defaults to 10.
    """
    if lat is None or lng is None:
        return {"source": "error", "resources": [], "error": "lat and lng are required."}

    radius = radius_miles if radius_miles and radius_miles > 0 else 10

    try:
        return _get_shelters(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        return {"source": "error", "resources": [], "error": str(exc)}


# ── Aggregate tool ────────────────────────────────────────────────────────────

@tool
def get_all_resources_tool(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Return food, hospital, and shelter resources near a location in one call.
    Useful when an agent needs a full picture without making three separate tool calls.
    lat and lng are required (WGS-84 decimal degrees).
    """
    if lat is None or lng is None:
        empty = {"source": "error", "resources": [], "error": "lat and lng are required."}
        return {"food": empty, "hospitals": empty, "shelters": empty}

    radius = radius_miles if radius_miles and radius_miles > 0 else 10

    # set up default error responses in case any individual fetch fails
    food_result     = {"source": "error", "resources": [], "error": ""}
    hospital_result = {"source": "error", "resources": [], "error": ""}
    shelter_result  = {"source": "error", "resources": [], "error": ""}

    # fetch each resource type independently so one failure doesn't block the others
    try:
        food_result = _get_food_resources(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        food_result["error"] = str(exc)

    try:
        hospital_result = _get_hospitals(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        hospital_result["error"] = str(exc)

    try:
        shelter_result = _get_shelters(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        shelter_result["error"] = str(exc)

    return {
        "food":      food_result,
        "hospitals": hospital_result,
        "shelters":  shelter_result,
    }


@tool
def create_bounds_tool(lat: float, lng: float, radius_miles: float = 25) -> dict:
    """
    Convert a center point (lat, lng) and radius (in miles) into a bounding box.
    Used by the risk agent to define the search area for USGS gauge stations.
    Returns a dict with north, south, east, west.
    """
    import math

    # convert miles to degrees latitude — 1 degree is roughly 69 miles everywhere
    lat_delta = radius_miles / 69.0

    # longitude degrees vary by latitude — near the equator they're wider,
    # near the poles they're narrower, so we adjust using cosine
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))

    return {
        "north": lat + lat_delta,
        "south": lat - lat_delta,
        "east":  lng + lng_delta,
        "west":  lng - lng_delta,
    }