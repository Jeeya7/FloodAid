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


# def get_all_usgs_stations(bounds: dict[str, float]) -> list[dict[str, Any]]:
#     """
#     USGS station ingestion with bounding-box filtering + deduplication.

#     Returns all active USGS gauges inside the bounding box.

#     USGS bBox order:
#         west,south,east,north
#     """

#     stations = []
#     seen = set()

#     bbox = f'{bounds["west"]},{bounds["south"]},{bounds["east"]},{bounds["north"]}'

#     params = {
#         "format": "json",
#         "siteStatus": "active",
#         "bBox": bbox,
#     }

#     r = requests.get(USGS_SITE_URL, params=params, timeout=60)

#     r.raise_for_status()

#     data = r.json()

#     time_series = data.get("value", {}).get("timeSeries", [])

#     for item in time_series:
#         try:
#             src = item["sourceInfo"]

#             site_id = src["siteCode"][0]["value"]

#             if site_id in seen:
#                 continue

#             seen.add(site_id)

#             geo = src.get("geoLocation", {}).get("geogLocation", {})

#             lat = geo.get("latitude")
#             lng = geo.get("longitude")

#             if lat is None or lng is None:
#                 continue

#             stations.append({
#                 "site_id": site_id,
#                 "name": src.get("siteName"),
#                 "lat": float(lat),
#                 "lng": float(lng),
#                 "state": src.get("siteProperty", [])
#             })

#         except Exception as e:
#             print(f"Skipping malformed station: {e}")
#             continue

#     return stations


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


def get_usgs_iv_data(station_id: str) -> dict[str, Any]:
    """
    Real-time USGS instantaneous values:
    - 00060: streamflow (cfs)
    - 00065: gage height (ft)
    """

    url = "https://waterservices.usgs.gov/nwis/iv/"

    params = {
        "format": "json",
        "sites": station_id,
        "parameterCd": "00060,00065"
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    result = {
        "station_id": station_id
    }

    try:
        series = data["value"]["timeSeries"]

        for s in series:
            var = s["variable"]["variableCode"][0]["value"]
            latest = s["values"][0]["value"][-1]["value"]

            if var == "00060":
                result["streamflow_cfs"] = float(latest)
            elif var == "00065":
                result["gage_height_ft"] = float(latest)

    except Exception:
        raise RuntimeError(f"Failed parsing IV data for {station_id}")

    return result


def get_usgs_dv_data(station_id: str, period: str = "P10Y") -> list[float]:
    """
    Historical streamflow values for percentile computation.
    """

    url = "https://waterservices.usgs.gov/nwis/dv/"

    params = {
        "format": "json",
        "sites": station_id,
        "parameterCd": "00060",
        "period": period
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    series = data["value"]["timeSeries"][0]["values"][0]["value"]

    values = []
    for v in series:
        if v["value"] != "-999999":
            try:
                values.append(float(v["value"]))
            except Exception:
                continue

    return values

import numpy as np


def compute_percentile(current_value: float, history: list[float]) -> float:
    """
    Returns percentile rank (0-100)
    """

    if not history:
        return 50.0

    return float(np.percentile(
        [v <= current_value for v in history],
        100
    ))


def compute_trend(values: list[float]) -> str:
    """
    Simple slope-based trend detection
    """

    if len(values) < 2:
        return "unknown"

    delta = values[-1] - values[-2]

    if delta > 0:
        return "rising"
    elif delta < 0:
        return "falling"
    else:
        return "steady"
    

def get_noaa_points(lat: float, lng: float) -> dict[str, Any]:
    """
    NOAA discovery endpoint:
    returns forecast + alerts URLs for a coordinate
    """

    url = f"https://api.weather.gov/points/{lat},{lng}"

    r = requests.get(url, timeout=10)
    r.raise_for_status()

    return r.json()


def get_noaa_rainfall_inches(lat: float, lng: float) -> float:
    """
    Approximate rainfall forecast from NOAA hourly grid
    """

    grid = get_noaa_points(lat, lng)
    url = grid["properties"]["forecastHourly"]

    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    periods = data["properties"]["periods"]

    rain = 0.0

    for p in periods[:12]:
        pop = p.get("probabilityOfPrecipitation", {}).get("value") or 0

        if pop > 60:
            rain += 0.2  # heuristic bucket

    return round(rain, 2)


def get_noaa_alert(lat: float, lng: float) -> str:
    """
    Active weather alerts for a point
    """

    url = f"https://api.weather.gov/alerts/active?point={lat},{lng}"

    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    features = data.get("features", [])

    if not features:
        return "none"

    for f in features:
        event = f["properties"]["event"].lower()
        if "flood" in event:
            return event

    return features[0]["properties"]["event"].lower()


def get_environmental_data(lat: float, lng: float, station_id: str) -> dict[str, Any]:
    """
    Unified hydrology + weather state for agent system
    """

    print("GET ENVINRONMENTAL DATA CALLED")

    iv = get_usgs_iv_data(station_id)
    dv = get_usgs_dv_data(station_id)

    rainfall = get_noaa_rainfall_inches(lat, lng)
    alert = get_noaa_alert(lat, lng)

    percentile = compute_percentile(iv.get("streamflow_cfs", 0), dv)
    trend = compute_trend(dv[-5:] if len(dv) > 5 else dv)

    return {
        "rain_forecast_inches": rainfall,
        "water_level_status": (
            "high" if iv.get("gage_height_ft", 0) > 20 else "normal"
        ),
        "streamflow_status": (
            "above_normal" if percentile > 70 else "normal"
        ),
        "weather_alert": alert,
        "nearest_gauge_distance_miles": None,  # plug spatial model later
        "water_level_trend": trend,
        "streamflow_cfs": iv.get("streamflow_cfs"),
        "gage_height_ft": iv.get("gage_height_ft"),
        "percentile_rank": percentile,
    }


def lookup_flood_stage(station_id: str) -> float | None:
    """
    Placeholder for flood stage metadata.

    In production this comes from:
    - NOAA AHPS (Advanced Hydrologic Prediction Service)
    - USGS site metadata (sometimes)
    - or a curated dataset
    """

    FLOOD_STAGE_DB = {
        "06893000": 25.0,
        "07032000": 28.0,
        "11447650": 25.0,
        "03253500": 30.0,
        "09380000": 20.0,
        "11490000": 12.0,
    }

    return FLOOD_STAGE_DB.get(station_id)


def get_water_station_state(station_id: str) -> dict[str, Any]:
    """
    Replaces _MOCK_WATER_DATA with real USGS-derived values.

    Output format matches your mock exactly:
    - gage_height_ft
    - flood_stage_ft (needs lookup or dataset)
    - streamflow_cfs
    - percentile_rank
    - water_level_trend
    """

    # -----------------------------
    # 1. Real-time data (USGS IV)
    # -----------------------------
    iv = get_usgs_iv_data(station_id)

    gage_height = iv.get("gage_height_ft", 0.0)
    streamflow = iv.get("streamflow_cfs", 0.0)

    # -----------------------------
    # 2. Historical data (USGS DV)
    # -----------------------------
    history = get_usgs_dv_data(station_id)

    percentile_rank = compute_percentile(streamflow, history)
    trend = compute_trend(history[-10:] if len(history) > 10 else history)

    # -----------------------------
    # 3. Flood stage (NOT in USGS IV reliably)
    #    You must supply or approximate this
    # -----------------------------
    flood_stage_ft = lookup_flood_stage(station_id)

    # fallback if unknown
    if flood_stage_ft is None:
        flood_stage_ft = gage_height * 1.1  # weak heuristic fallback

    # -----------------------------
    # 4. Final standardized object
    # -----------------------------
    return {
        "station_id": station_id,
        "gage_height_ft": round(gage_height, 2),
        "flood_stage_ft": round(flood_stage_ft, 2),
        "streamflow_cfs": int(streamflow),
        "percentile_rank": float(percentile_rank),
        "water_level_trend": trend,
    }


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
    "11490000": {
        "station_id": "11490000",
        "gage_height_ft": 9.8,
        "flood_stage_ft": 12.0,
        "streamflow_cfs": 5_600,
        "percentile_rank": 68,
        "water_level_trend": "rising",
    },
}


def get_gauges_by_bounds(bounds: dict[str, float] | None = None) -> list[dict[str, Any]]:

    """
    USGS station ingestion with bounding-box filtering + deduplication.

    Returns all active USGS gauges inside the bounding box.

    USGS bBox order:
        west,south,east,north
    """

    if bounds is None: 
        bounds = DEFAULT_BOUNDS

    stations = []
    seen = set()

    bbox = f'{bounds["west"]},{bounds["south"]},{bounds["east"]},{bounds["north"]}'

    params = {
        "format": "json",
        "siteStatus": "active",
        "bBox": bbox,
    }

    r = requests.get(USGS_SITE_URL, params=params, timeout=60)

    r.raise_for_status()

    data = r.json()

    time_series = data.get("value", {}).get("timeSeries", [])

    for item in time_series:
        try:
            src = item["sourceInfo"]

            site_id = src["siteCode"][0]["value"]

            if site_id in seen:
                continue

            seen.add(site_id)

            geo = src.get("geoLocation", {}).get("geogLocation", {})

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

        except Exception as e:
            print(f"Skipping malformed station: {e}")
            continue

    return stations



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