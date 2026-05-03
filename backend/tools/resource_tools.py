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

from services.food_service import get_food_resources as _get_food_resources
from services.hospital_service import get_hospitals as _get_hospitals
from services.shelter_service import get_shelters as _get_shelters


# ── Individual resource tools ─────────────────────────────────────────────────

@tool
def get_food_resources_tool(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Return food-assistance resources (food banks, meal sites, pantries) near a location.

    lat and lng are required (WGS-84 decimal degrees).
    radius_miles controls the search radius; defaults to 10.

    Returns:
      source    : "food_api" when live, "mock_food_api" when falling back
      resources : list of food resource dicts
    """
    if lat is None or lng is None:
        return {"source": "error", "resources": [], "error": "lat and lng are required."}

    radius = radius_miles if radius_miles and radius_miles > 0 else 10

    try:
        return _get_food_resources(lat=lat, lng=lng, radius_miles=radius)
    except Exception as exc:
        return {"source": "error", "resources": [], "error": str(exc)}


@tool
def get_hospitals_tool(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Return hospital and medical resources (hospitals, urgent care, clinics) near a location.

    lat and lng are required (WGS-84 decimal degrees).
    radius_miles controls the search radius; defaults to 10.

    Returns:
      source    : "hospital_api" when live, "mock_hospital_api" when falling back
      resources : list of hospital resource dicts, each with an emergency_services flag
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

    Returns:
      source    : "shelter_api" when live, "mock_shelter_api" when falling back
      resources : list of shelter dicts, each with a capacity field (int or null)
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

    Useful when an agent needs a full picture of available emergency resources
    without making three separate tool calls.

    lat and lng are required (WGS-84 decimal degrees).
    radius_miles controls the search radius for all three resource types; defaults to 10.

    Returns:
      food      : result from get_food_resources
      hospitals : result from get_hospitals
      shelters  : result from get_shelters
    """
    if lat is None or lng is None:
        empty = {"source": "error", "resources": [], "error": "lat and lng are required."}
        return {"food": empty, "hospitals": empty, "shelters": empty}

    radius = radius_miles if radius_miles and radius_miles > 0 else 10

    food_result     = {"source": "error", "resources": [], "error": ""}
    hospital_result = {"source": "error", "resources": [], "error": ""}
    shelter_result  = {"source": "error", "resources": [], "error": ""}

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

    Returns a dict with:
    north, south, east, west

    Notes:
    - Uses simple geographic approximation (1 degree ≈ 69 miles)
    - Good enough for regional flood analysis
    """

    # Convert miles → degrees latitude
    lat_delta = radius_miles / 69.0

    # Convert miles → degrees longitude (adjust for latitude)
    import math
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))

    bounds = {
        "north": lat + lat_delta,
        "south": lat - lat_delta,
        "east": lng + lng_delta,
        "west": lng - lng_delta,
    }

    return bounds