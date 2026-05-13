
# tools/risk_region_tools.py
#
# LangChain @tool-decorated wrappers around the environmental services.
# The @tool decorator registers each function so LangGraph's ReAct agent
# can discover, call, and reason about them automatically.
#
# Rules:
#   - Tools only fetch and return normalised data.
#   - Tools do NOT score risk or make decisions.
#   - All real logic lives in the services they call.

from langchain_core.tools import tool

# re-exported so the agent never has to import directly from services
from services.usgs_service    import DEFAULT_BOUNDS
from services.usgs_service    import get_gauges_by_bounds as _get_gauges_by_bounds
from services.usgs_service    import get_usgs_water_data  as _get_usgs_water_data
from services.weather_service import get_weather_context  as _get_weather_context


@tool
def get_gauges_by_bounds_tool(bounds: dict) -> list:
    """
    Return all USGS gauge stations within a lat/lng bounding box.
    bounds must have keys: north, south, east, west (floats, WGS-84).
    Pass an empty dict {} to use the default contiguous U.S. bounds.
    Each returned gauge has: station_id, name, lat, lng, river_name.
    """
    # if no bounds passed, fall back to the full US bounding box
    return _get_gauges_by_bounds(bounds or None)


@tool
def get_usgs_water_data_tool(station_id: str) -> dict:
    """
    Return current water-level data for a single USGS gauge station.
    Returns: station_id, gage_height_ft, flood_stage_ft,
             streamflow_cfs, percentile_rank, water_level_trend.
    """
    return _get_usgs_water_data(station_id)


@tool
def get_weather_context_tool(lat: float, lng: float) -> dict:
    """
    Return NWS weather forecast and alert context for a lat/lng location.
    Returns: weather_alert, rain_forecast_inches, rain_next_6hr_inches,
             storm_probability, forecast_summary.
    """
    return _get_weather_context(lat, lng)


@tool
def create_bounds_tool(lat: float, lng: float, radius_miles: float = 25) -> dict:
    """
    Convert a center point (lat, lng) and radius (in miles) into a bounding box.
    Used by the risk agent before calling get_gauges_by_bounds_tool.
    Returns a dict with north, south, east, west.
    """
    import math

    # 1 degree of latitude is always roughly 69 miles
    lat_delta = radius_miles / 69.0

    # longitude degrees shrink as you move toward the poles
    # cosine adjusts for this so the box is accurate at any latitude
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))

    return {
        "north": round(lat + lat_delta, 4),
        "south": round(lat - lat_delta, 4),
        "east":  round(lng + lng_delta, 4),
        "west":  round(lng - lng_delta, 4),
    }
