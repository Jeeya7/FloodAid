# usgs_service.py
# Simulates calls to the USGS Water Services API.
# In production, replace mock data with real HTTP requests to:
#   https://waterservices.usgs.gov/nwis/

from typing import Any
import requests

# Default bounds covering the contiguous United States
DEFAULT_BOUNDS: dict[str, float] = {
    "north": 49.384358,
    "south": 24.396308,
    "east": -66.93457,
    "west": -125.0,
}

USGS_SITE_URL = "https://waterservices.usgs.gov/nwis/iv"

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