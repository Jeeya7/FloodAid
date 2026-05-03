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

from services.usgs_service import DEFAULT_BOUNDS  # re-exported so agent never imports services
from services.usgs_service import get_gauges_by_bounds as _get_gauges_by_bounds
from services.usgs_service import get_usgs_water_data as _get_usgs_water_data
from services.water_services_service import get_streamflow_context as _get_streamflow_context
from services.weather_service import get_weather_context as _get_weather_context


@tool
def get_gauges_by_bounds_tool(bounds: dict) -> list:
    """
    Return all USGS gauge stations within a lat/lng bounding box.

    bounds must have keys: north, south, east, west (floats, WGS-84).
    Pass an empty dict {} to use the default contiguous U.S. bounds.

    Each returned gauge has: station_id, name, lat, lng, river_name.
    """
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
def get_streamflow_context_tool(station_id: str) -> dict:
    """
    Return streamflow anomaly context for a given station.

    Returns: station_id, streamflow_status, percent_difference,
             anomaly_level, notes.
    """
    return _get_streamflow_context(station_id)


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
