# weather_service.py
# Simulates calls to the National Weather Service (NWS) API.
# In production, replace mock data with real HTTP requests to:
#   https://api.weather.gov/

from typing import Any
import requests

# Mock weather context keyed by approximate location label.
# We bucket stations by a rough lat/lng key so lookups stay simple.
# Each entry mirrors the shape of a real NWS point-forecast response.

_MOCK_WEATHER: list[dict[str, Any]] = [
    # Missouri River at Kansas City area
    {
        "_lat_center": 39.1,
        "_lng_center": -94.6,
        "_radius_deg": 2.0,
        "weather_alert": "flood_warning",
        "rain_forecast_inches": 3.2,
        "rain_next_6hr_inches": 1.1,
        "storm_probability": 0.85,
        "forecast_summary": "Severe thunderstorm system moving northeast; flash flooding imminent.",
    },
    # Mississippi River at Memphis area
    {
        "_lat_center": 35.1,
        "_lng_center": -90.0,
        "_radius_deg": 2.0,
        "weather_alert": "flood_watch",
        "rain_forecast_inches": 2.2,
        "rain_next_6hr_inches": 0.8,
        "storm_probability": 0.65,
        "forecast_summary": "Slow-moving low-pressure system; widespread heavy rain expected.",
    },
    # Sacramento River area
    {
        "_lat_center": 38.6,
        "_lng_center": -121.5,
        "_radius_deg": 2.0,
        "weather_alert": "flood_watch",
        "rain_forecast_inches": 1.8,
        "rain_next_6hr_inches": 0.5,
        "storm_probability": 0.55,
        "forecast_summary": "Atmospheric river event approaching the Central Valley.",
    },
    # Ohio River at Cincinnati area
    {
        "_lat_center": 39.1,
        "_lng_center": -84.5,
        "_radius_deg": 2.0,
        "weather_alert": "flood_watch",
        "rain_forecast_inches": 2.1,
        "rain_next_6hr_inches": 0.6,
        "storm_probability": 0.60,
        "forecast_summary": "Active spring weather pattern; multiple rounds of heavy rain possible.",
    },
    # Colorado River near Grand Canyon — dry / normal
    {
        "_lat_center": 36.1,
        "_lng_center": -112.0,
        "_radius_deg": 2.0,
        "weather_alert": "none",
        "rain_forecast_inches": 0.3,
        "rain_next_6hr_inches": 0.0,
        "storm_probability": 0.10,
        "forecast_summary": "Clear and dry conditions expected for the next 48 hours.",
    },
]

_DEFAULT_WEATHER: dict[str, Any] = {
    "weather_alert": "none",
    "rain_forecast_inches": 0.0,
    "rain_next_6hr_inches": 0.0,
    "storm_probability": 0.0,
    "forecast_summary": "No weather data available for this location.",
}


def _distance_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Rough Euclidean distance in degrees — good enough for mock bucketing."""
    return ((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2) ** 0.5


def get_weather_context(lat: float, lng: float) -> dict[str, Any]:
    """
    Return weather forecast and alert context for a lat/lng location.

    In production this would call:
      GET https://api.weather.gov/points/{lat},{lng}  →  then fetch the forecast URL
    For now, we return the nearest mock entry within its radius.
    """
    best_match = None
    best_dist = float("inf")

    for entry in _MOCK_WEATHER:
        dist = _distance_deg(lat, lng, entry["_lat_center"], entry["_lng_center"])
        if dist < entry["_radius_deg"] and dist < best_dist:
            best_dist = dist
            best_match = entry

    if best_match is None:
        return _DEFAULT_WEATHER.copy()

    # Strip internal bucketing keys before returning
    return {k: v for k, v in best_match.items() if not k.startswith("_")}

##############################################################################


def get_weather_grid(lat: float, lng: float) -> dict[str, Any]:
    url = f"https://api.weather.gov/points/{lat},{lng}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_hourly_rainfall(lat: float, lng: float) -> float:
    grid = get_weather_grid(lat, lng)
    forecast_url = grid["properties"]["forecastHourly"]

    r = requests.get(forecast_url, timeout=10)
    r.raise_for_status()
    data = r.json()

    periods = data["properties"]["periods"]

    # next ~12–24 hours rainfall estimate
    rain_inches = 0.0

    for p in periods[:12]:
        # precipitationProbability is % chance
        pop = p.get("probabilityOfPrecipitation", {}).get("value") or 0
        if pop > 50:
            rain_inches += 0.15  # heuristic bucket (you can improve later)

    return round(rain_inches, 2)


def get_weather_alert(lat: float, lng: float) -> str:
    url = f"https://api.weather.gov/alerts/active?point={lat},{lng}"
    
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    features = data.get("features", [])

    if not features:
        return "none"

    # prioritize flood-related alerts
    for f in features:
        event = f["properties"]["event"].lower()
        if "flood" in event:
            return event

    return features[0]["properties"]["event"].lower()