# usgs_service.py
# Fetches real water level and gauge station data from the USGS Water Services API.
# Note: the "simulates" comment was left over from when we used mock data —
# this now makes real HTTP requests to https://waterservices.usgs.gov/nwis/

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# default bounding box covers the whole contiguous US
# used as a fallback if no bounds are passed in
DEFAULT_BOUNDS: dict[str, float] = {
    "north": 49.384358,
    "south": 24.396308,
    "east": -66.93457,
    "west": -125.0,
}

USGS_SITE_URL = "https://waterservices.usgs.gov/nwis/iv"
USGS_BASE     = "https://waterservices.usgs.gov/nwis"

_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@beaverhacks.com)",
    "Accept": "application/json",
}

_TIMEOUT = (5, 20)  # (connect timeout, read timeout) in seconds

# returned when the real API call fails so the agent still gets something
_DEFAULT_WATER: dict[str, Any] = {
    "station_id":        "unknown",
    "gage_height_ft":    0.0,
    "flood_stage_ft":    20.0,
    "streamflow_cfs":    0,
    "percentile_rank":   0.0,
    "water_level_trend": "unknown",
}

# hardcoded flood stage thresholds for known stations
# ideally this would come from NOAA AHPS but this works for now
_FLOOD_STAGE_DB = {
    "06893000": 25.0,
    "07032000": 28.0,
    "11447650": 25.0,
    "03253500": 30.0,
    "09380000": 20.0,
    "11490000": 12.0,
}


def _make_session() -> requests.Session:
    # creates a requests session with automatic retries
    # so temporary USGS outages don't crash the whole pipeline
    session = requests.Session()
    session.headers.update(_HEADERS)

    retry = Retry(
        total=3,                               # retry up to 3 times
        backoff_factor=0.5,                    # wait 0.5s, 1s, 2s between retries
        status_forcelist={500, 502, 503, 504}, # only retry on server errors
        allowed_methods={"GET"},
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# single shared session so we reuse the TCP connection across calls
_SESSION = _make_session()


def _get(url: str) -> dict[str, Any]:
    # simple wrapper around session.get that raises on non-200 responses
    resp = _SESSION.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _compute_percentile(current: float, history: list[float]) -> float:
    # calculates what percentage of historical values are below the current value
    # e.g. 90th percentile means the river is higher than 90% of past readings
    if not history:
        return 50.0
    lower = sum(v <= current for v in history)
    return round((lower / len(history)) * 100, 1)


def _compute_trend(values: list[float]) -> str:
    # compares the last two readings to determine if water is rising or falling
    if len(values) < 2:
        return "unknown"
    delta = values[-1] - values[-2]
    if delta > 0:
        return "rising"
    if delta < 0:
        return "falling"
    return "steady"


def _get_iv_data(station_id: str) -> dict[str, float]:
    # fetches real-time (instantaneous value) data for a station
    # parameterCd=00060 is streamflow, 00065 is gage height
    data = _get(
        f"{USGS_BASE}/iv/?format=json&sites={station_id}&parameterCd=00060,00065"
    )

    result = {}
    for series in data.get("value", {}).get("timeSeries", []):
        code   = series["variable"]["variableCode"][0]["value"]
        values = series["values"][0]["value"]

        if not values:
            continue

        latest = float(values[-1]["value"])

        if code == "00060":
            result["streamflow_cfs"] = latest   # cubic feet per second
        elif code == "00065":
            result["gage_height_ft"] = latest   # feet above gauge datum

    return result


def _get_dv_data(station_id: str) -> list[float]:
    # fetches 30 days of daily average streamflow for historical comparison
    # we use this to calculate percentile rank and trend
    data = _get(
        f"{USGS_BASE}/dv/?format=json&sites={station_id}&parameterCd=00060&period=P30D"
    )

    try:
        values = data["value"]["timeSeries"][0]["values"][0]["value"]
        return [
            float(v["value"])
            for v in values
            if v["value"] != "-999999"  # USGS uses -999999 for missing data
        ]
    except Exception:
        return []


def get_usgs_water_data(station_id: str) -> dict[str, Any]:
    """
    Fetches real USGS water conditions for a station.
    Returns gage height, streamflow, flood stage, percentile rank, and trend.
    """
    try:
        # step 1 — get current real-time readings
        iv          = _get_iv_data(station_id)
        gage_height = iv.get("gage_height_ft", 0.0)
        streamflow  = iv.get("streamflow_cfs", 0.0)

        # step 2 — get 30 days of history for context
        history           = _get_dv_data(station_id)
        percentile_rank   = _compute_percentile(streamflow, history)
        water_level_trend = _compute_trend(history[-10:])  # last 10 days for trend

        # step 3 — look up flood stage for this station
        # if we don't have it hardcoded, estimate it as 10% above current level
        flood_stage_ft = _FLOOD_STAGE_DB.get(
            station_id,
            max(gage_height * 1.1, 20.0),
        )

        return {
            "station_id":        station_id,
            "gage_height_ft":    round(gage_height, 2),
            "flood_stage_ft":    round(flood_stage_ft, 2),
            "streamflow_cfs":    int(streamflow),
            "percentile_rank":   percentile_rank,
            "water_level_trend": water_level_trend,
        }

    except Exception as e:
        # if anything fails return the default so the agent still gets data
        print(f"[water_service] Failed for {station_id}: {e}")
        fallback = _DEFAULT_WATER.copy()
        fallback["station_id"] = station_id
        return fallback


def get_gauges_by_bounds(
    bounds: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch active USGS stream gauges inside a bounding box.
    Returns a list of gauge objects with site_id, name, lat, lng.
    """
    bounds = bounds or DEFAULT_BOUNDS
    _validate_bounds(bounds)

    # USGS expects the bounding box as: west,south,east,north
    bbox = (
        f'{bounds["west"]},'
        f'{bounds["south"]},'
        f'{bounds["east"]},'
        f'{bounds["north"]}'
    )

    response = requests.get(
        USGS_SITE_URL,
        params={
            "format":     "json",
            "siteStatus": "active",  # only currently active stations
            "siteType":   "ST",      # ST = stream gauges only
            "bBox":       bbox,
        },
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    return _parse_usgs_station_payload(payload)


def _validate_bounds(bounds: dict[str, float]) -> None:
    # makes sure the bounding box makes geographic sense before sending to USGS
    required = {"west", "south", "east", "north"}
    missing  = required - bounds.keys()

    if missing:
        raise ValueError(f"Missing bounding box keys: {missing}")
    if bounds["west"] >= bounds["east"]:
        raise ValueError("west must be less than east")
    if bounds["south"] >= bounds["north"]:
        raise ValueError("south must be less than north")


def _parse_usgs_station_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    # pulls the list of stations out of the raw USGS response
    # deduplicates by site_id because the same station appears once per
    # parameter type (e.g. streamflow and gage height are separate entries)
    stations: list[dict[str, Any]] = []
    seen:     set[str]             = set()

    time_series = payload.get("value", {}).get("timeSeries", [])

    for item in time_series:
        station = _normalize_station(item)

        if station is None:
            continue

        site_id = station["site_id"]

        if site_id in seen:
            continue  # already added this station from a different parameter

        seen.add(site_id)
        stations.append(station)

    return stations


def _normalize_station(
    item: dict[str, Any],
) -> dict[str, Any] | None:
    # converts a raw USGS time series record into our simple gauge format
    # returns None if the record is missing required fields
    try:
        source  = item["sourceInfo"]
        site_id = source["siteCode"][0]["value"]
        geo     = source["geoLocation"]["geogLocation"]
        lat     = geo["latitude"]
        lng     = geo["longitude"]

        return {
            "site_id": site_id,
            "name":    source.get("siteName", ""),
            "lat":     float(lat),
            "lng":     float(lng),
        }

    except (KeyError, TypeError, ValueError):
        # malformed record — skip it silently
        return None