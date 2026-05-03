# usgs_service.py
# Simulates calls to the USGS Water Services API.
# In production, replace mock data with real HTTP requests to:
#   https://waterservices.usgs.gov/nwis/

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Default bounds covering the contiguous United States
DEFAULT_BOUNDS: dict[str, float] = {
    "north": 49.384358,
    "south": 24.396308,
    "east": -66.93457,
    "west": -125.0,
}

USGS_SITE_URL = "https://waterservices.usgs.gov/nwis/iv"


# water_service.py
# Calls the real USGS water services API.
# https://waterservices.usgs.gov/


USGS_BASE = "https://waterservices.usgs.gov/nwis"

_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@beaverhacks.com)",
    "Accept": "application/json",
}

_TIMEOUT = (5, 20)

_DEFAULT_WATER: dict[str, Any] = {
    "station_id": "unknown",
    "gage_height_ft": 0.0,
    "flood_stage_ft": 20.0,
    "streamflow_cfs": 0,
    "percentile_rank": 0.0,
    "water_level_trend": "unknown",
}


# Static flood-stage lookup
# Replace with NOAA AHPS / database later
_FLOOD_STAGE_DB = {
    "06893000": 25.0,
    "07032000": 28.0,
    "11447650": 25.0,
    "03253500": 30.0,
    "09380000": 20.0,
    "11490000": 12.0,
}


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist={500, 502, 503, 504},
        allowed_methods={"GET"},
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


_SESSION = _make_session()


def _get(url: str) -> dict[str, Any]:
    resp = _SESSION.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _compute_percentile(current: float, history: list[float]) -> float:
    if not history:
        return 50.0

    lower = sum(v <= current for v in history)
    return round((lower / len(history)) * 100, 1)


def _compute_trend(values: list[float]) -> str:
    if len(values) < 2:
        return "unknown"

    delta = values[-1] - values[-2]

    if delta > 0:
        return "rising"
    if delta < 0:
        return "falling"
    return "steady"


def _get_iv_data(station_id: str) -> dict[str, float]:
    data = _get(
        f"{USGS_BASE}/iv/?format=json&sites={station_id}&parameterCd=00060,00065"
    )

    result = {}

    for series in data.get("value", {}).get("timeSeries", []):
        code = series["variable"]["variableCode"][0]["value"]
        values = series["values"][0]["value"]

        if not values:
            continue

        latest = float(values[-1]["value"])

        if code == "00060":
            result["streamflow_cfs"] = latest
        elif code == "00065":
            result["gage_height_ft"] = latest

    return result


def _get_dv_data(station_id: str) -> list[float]:
    data = _get(
        f"{USGS_BASE}/dv/?format=json&sites={station_id}&parameterCd=00060&period=P30D"
    )

    try:
        values = data["value"]["timeSeries"][0]["values"][0]["value"]

        return [
            float(v["value"])
            for v in values
            if v["value"] != "-999999"
        ]

    except Exception:
        return []


def get_usgs_water_data(station_id: str) -> dict[str, Any]:
    """
    Fetches real USGS water conditions for a station.

    Returns same structure as old mock water data.
    """

    try:
        # Step 1 — real-time data
        iv = _get_iv_data(station_id)

        gage_height = iv.get("gage_height_ft", 0.0)
        streamflow = iv.get("streamflow_cfs", 0.0)

        # Step 2 — historical context
        history = _get_dv_data(station_id)

        percentile_rank = _compute_percentile(streamflow, history)
        water_level_trend = _compute_trend(history[-10:])

        # Step 3 — flood stage lookup
        flood_stage_ft = _FLOOD_STAGE_DB.get(
            station_id,
            max(gage_height * 1.1, 20.0),
        )

        return {
            "station_id": station_id,
            "gage_height_ft": round(gage_height, 2),
            "flood_stage_ft": round(flood_stage_ft, 2),
            "streamflow_cfs": int(streamflow),
            "percentile_rank": percentile_rank,
            "water_level_trend": water_level_trend,
        }

    except Exception as e:
        print(f"[water_service] Failed for {station_id}: {e}")

        fallback = _DEFAULT_WATER.copy()
        fallback["station_id"] = station_id
        return fallback
    

def get_gauges_by_bounds(
    bounds: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch active USGS gauges inside a bounding box.

    Args:
        bounds:
            Bounding box using:
            {
                "west": float,
                "south": float,
                "east": float,
                "north": float,
            }

    Returns:
        List of normalized gauge objects:
        [
            {
                "site_id": str,
                "name": str,
                "lat": float,
                "lng": float,
            }
        ]

    Notes:
        USGS bBox ordering:
            west,south,east,north
    """

    bounds = bounds or DEFAULT_BOUNDS
    _validate_bounds(bounds)

    bbox = (
        f'{bounds["west"]},'
        f'{bounds["south"]},'
        f'{bounds["east"]},'
        f'{bounds["north"]}'
    )

    response = requests.get(
        USGS_SITE_URL,
        params={
            "format": "json",
            "siteStatus": "active",
            "siteType": "ST",
            "bBox": bbox,
        },
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()

    return _parse_usgs_station_payload(payload)


def _validate_bounds(bounds: dict[str, float]) -> None:
    """
    Validate bounding box structure.
    """

    required = {"west", "south", "east", "north"}

    missing = required - bounds.keys()
    if missing:
        raise ValueError(f"Missing bounding box keys: {missing}")

    if bounds["west"] >= bounds["east"]:
        raise ValueError("west must be less than east")

    if bounds["south"] >= bounds["north"]:
        raise ValueError("south must be less than north")


def _parse_usgs_station_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Normalize USGS station response into internal gauge schema.
    """

    stations: list[dict[str, Any]] = []
    seen: set[str] = set()

    time_series = payload.get("value", {}).get("timeSeries", [])

    for item in time_series:
        station = _normalize_station(item)

        if station is None:
            continue

        site_id = station["site_id"]

        if site_id in seen:
            continue

        seen.add(site_id)
        stations.append(station)

    return stations


def _normalize_station(
    item: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Convert raw USGS station record into internal format.
    """

    try:
        source = item["sourceInfo"]

        site_id = source["siteCode"][0]["value"]

        geo = source["geoLocation"]["geogLocation"]

        lat = geo["latitude"]
        lng = geo["longitude"]

        return {
            "site_id": site_id,
            "name": source.get("siteName", ""),
            "lat": float(lat),
            "lng": float(lng),
        }

    except (KeyError, TypeError, ValueError):
        return None