# usgs_service.py
# Simulates calls to the USGS Water Services API.
# In production, replace mock data with real HTTP requests to:
#   https://waterservices.usgs.gov/nwis/

from typing import Any

# Default bounds covering the contiguous United States
DEFAULT_BOUNDS: dict[str, float] = {
    "north": 49.384358,
    "south": 24.396308,
    "east": -66.93457,
    "west": -125.0,
}

# Mock gauge locations spread across the U.S.
_MOCK_GAUGES = [
    {
        "station_id": "06893000",
        "name": "Missouri River at Kansas City, MO",
        "lat": 39.1131,
        "lng": -94.6275,
        "river_name": "Missouri River",
    },
    {
        "station_id": "07032000",
        "name": "Mississippi River at Memphis, TN",
        "lat": 35.1495,
        "lng": -90.0490,
        "river_name": "Mississippi River",
    },
    {
        "station_id": "11447650",
        "name": "Sacramento River at Sacramento, CA",
        "lat": 38.5816,
        "lng": -121.4944,
        "river_name": "Sacramento River",
    },
    {
        "station_id": "03253500",
        "name": "Ohio River at Cincinnati, OH",
        "lat": 39.1031,
        "lng": -84.5120,
        "river_name": "Ohio River",
    },
    {
        "station_id": "09380000",
        "name": "Colorado River near Grand Canyon, AZ",
        "lat": 36.0544,
        "lng": -111.9873,
        "river_name": "Colorado River",
    },
]

# Mock water-level readings per station.
# Each entry is shaped like a real USGS instantaneous values response.
_MOCK_WATER_DATA: dict[str, dict[str, Any]] = {
    # HIGH RISK: above flood stage, rising, very high percentile
    "06893000": {
        "station_id": "06893000",
        "gage_height_ft": 28.4,
        "flood_stage_ft": 25.0,
        "streamflow_cfs": 189_000,
        "percentile_rank": 92,
        "water_level_trend": "rising",
    },
    # HIGH RISK: well above flood stage, fast rise
    "07032000": {
        "station_id": "07032000",
        "gage_height_ft": 32.1,
        "flood_stage_ft": 28.0,
        "streamflow_cfs": 1_250_000,
        "percentile_rank": 95,
        "water_level_trend": "rising",
    },
    # MODERATE RISK: below flood stage but rising with heavy rain forecast
    "11447650": {
        "station_id": "11447650",
        "gage_height_ft": 18.3,
        "flood_stage_ft": 25.0,
        "streamflow_cfs": 42_000,
        "percentile_rank": 75,
        "water_level_trend": "rising",
    },
    # MODERATE RISK: elevated flow, active flood watch
    "03253500": {
        "station_id": "03253500",
        "gage_height_ft": 22.0,
        "flood_stage_ft": 30.0,
        "streamflow_cfs": 98_000,
        "percentile_rank": 80,
        "water_level_trend": "steady",
    },
    # LOW RISK: normal levels, no alerts
    "09380000": {
        "station_id": "09380000",
        "gage_height_ft": 8.1,
        "flood_stage_ft": 20.0,
        "streamflow_cfs": 14_200,
        "percentile_rank": 30,
        "water_level_trend": "steady",
    },
}


def get_gauges_by_bounds(bounds: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """
    Return gauge stations that fall within the given lat/lng bounds.

    In production this would call:
      GET https://waterservices.usgs.gov/nwis/iv/?bbox=west,south,east,north&...
    For now it filters the mock list by bounding box.
    """
    if bounds is None:
        bounds = DEFAULT_BOUNDS

    result = []
    for gauge in _MOCK_GAUGES:
        if (
            bounds["south"] <= gauge["lat"] <= bounds["north"]
            and bounds["west"] <= gauge["lng"] <= bounds["east"]
        ):
            result.append(gauge)

    return result


def get_usgs_water_data(station_id: str) -> dict[str, Any]:
    """
    Return current water-level data for a single USGS gauge station.

    In production this would call:
      GET https://waterservices.usgs.gov/nwis/iv/?sites=<station_id>&...
    """
    return _MOCK_WATER_DATA.get(
        station_id,
        {
            "station_id": station_id,
            "gage_height_ft": 0.0,
            "flood_stage_ft": 20.0,
            "streamflow_cfs": 0,
            "percentile_rank": 0,
            "water_level_trend": "unknown",
        },
    )
