# usgs_service.py
# Simulates calls to the USGS Water Services API.
# In production, replace mock data with real HTTP requests to:
#   https://waterservices.usgs.gov/nwis/

from typing import Any
import requests
import numpy as np
from sklearn.neighbors import BallTree

# Default bounds covering the contiguous United States
DEFAULT_BOUNDS: dict[str, float] = {
    "north": 49.384358,
    "south": 24.396308,
    "east": -66.93457,
    "west": -125.0,
}

USGS_SITE_URL = "https://waterservices.usgs.gov/nwis/iv"


def get_all_usgs_stations() -> list[dict[str, Any]]:
    """
    USGS station ingestion with deduplication.
    Returns all active USGS gauges with coordinates.
    """

    stations = []
    seen = set()

    start_index = 0
    params = {
        "format": "json",
        "siteStatus": "all",          # stream sites (important for flood modeling)
        "stateCd" : "or",
    }

    r = requests.get(USGS_SITE_URL, params=params, timeout=60)
    print("here")

    data = r.json()

    time_series = data.get("value", {}).get("timeSeries", [])

    for item in time_series:
        try:
            src = item["sourceInfo"]

            site_id = src["siteCode"][0]["value"]

            if site_id in seen:
                continue
            seen.add(site_id)

            geo = src.get("geoLocation", {}) \
                        .get("geogLocation", {})

            lat = geo.get("latitude")
            lng = geo.get("longitude")

            if lat is None or lng is None:
                continue

            stations.append({
                "site_id": site_id,
                "name": src.get("siteName"),
                "lat": float(lat),
                "lng": float(lng),
                "state": src.get("siteProperty", [])
            })

        except Exception:
            continue


    return stations


# # Mock gauge locations spread across the U.S.
# _MOCK_GAUGES = [
#     {
#         "station_id": "06893000",
#         "name": "Missouri River at Kansas City, MO",
#         "lat": 39.1131,
#         "lng": -94.6275,
#         "river_name": "Missouri River",
#     },
#     {
#         "station_id": "07032000",
#         "name": "Mississippi River at Memphis, TN",
#         "lat": 35.1495,
#         "lng": -90.0490,
#         "river_name": "Mississippi River",
#     },
#     {
#         "station_id": "11447650",
#         "name": "Sacramento River at Sacramento, CA",
#         "lat": 38.5816,
#         "lng": -121.4944,
#         "river_name": "Sacramento River",
#     },
#     {
#         "station_id": "03253500",
#         "name": "Ohio River at Cincinnati, OH",
#         "lat": 39.1031,
#         "lng": -84.5120,
#         "river_name": "Ohio River",
#     },
#     {
#         "station_id": "09380000",
#         "name": "Colorado River near Grand Canyon, AZ",
#         "lat": 36.0544,
#         "lng": -111.9873,
#         "river_name": "Colorado River",
#     },
# ]


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
    for gauge in get_all_usgs_stations():
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



class USGSStationIndex:
    def __init__(self, stations: list[dict]):
        self.stations = stations

        coords = np.array([
            [s["lat"], s["lng"]] for s in stations
        ])

        # convert degrees → radians for haversine
        self.tree = BallTree(np.radians(coords), metric="haversine")

    def nearest(self, lat: float, lng: float, k: int = 3):
        dist, idx = self.tree.query(
            np.radians([[lat, lng]]),
            k=k
        )

        results = []
        for i in idx[0]:
            results.append(self.stations[i])

        return results
    

def get_usgs_streamflow(site_id: str) -> dict[str, Any]:
    url = "https://waterservices.usgs.gov/nwis/iv/"
    
    params = {
        "format": "json",
        "sites": site_id,
        "parameterCd": "00060",  # discharge (flow rate)
        "siteStatus": "all"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    values = data["value"]["timeSeries"][0]["values"][0]["value"]

    latest = float(values[-1]["value"])
    previous = float(values[-2]["value"]) if len(values) > 1 else latest

    trend = (
        "rising" if latest > previous
        else "falling" if latest < previous
        else "stable"
    )

    return {
        "streamflow_cfs": latest,
        "trend": trend,
    }


def aggregate_risk(features: list[dict]) -> dict:
    """
    Simple baseline fusion model
    """

    avg_flow = sum(f["streamflow"] for f in features) / len(features)
    rising = sum(1 for f in features if f["trend"] == "rising")

    flood_risk_score = (
        0.5 * min(avg_flow / 2000, 1.0) +
        0.5 * (rising / len(features))
    )

    return {
        "flood_risk_score": round(flood_risk_score, 3),
        "risk_level": (
            "high" if flood_risk_score > 0.7
            else "moderate" if flood_risk_score > 0.4
            else "low"
        )
    }