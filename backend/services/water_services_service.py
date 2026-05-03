# weather_service.py
# Calls the National Weather Service (NWS) API.
# https://api.weather.gov/

import urllib.request
import urllib.error
import json
from typing import Any

NWS_BASE = "https://api.weather.gov"

_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@example.com)",  # NWS requires a User-Agent
    "Accept": "application/geo+json",
}

_DEFAULT_WEATHER: dict[str, Any] = {
    "weather_alert": "none",
    "rain_forecast_inches": 0.0,
    "rain_next_6hr_inches": 0.0,
    "storm_probability": 0.0,
    "forecast_summary": "No weather data available for this location.",
}


def _get(url: str) -> dict[str, Any]:
    """Simple GET request to NWS API."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_active_alerts(lat: float, lng: float) -> str:
    """
    Returns the highest active alert level for a location.
    GET https://api.weather.gov/alerts/active?point={lat},{lng}
    """
    try:
        url = f"{NWS_BASE}/alerts/active?point={lat},{lng}"
        data = _get(url)
        features = data.get("features", [])

        # Priority order
        alert_priority = {
            "Flood Warning": "flood_warning",
            "Flash Flood Warning": "flood_warning",
            "Flood Watch": "flood_watch",
            "Flash Flood Watch": "flood_watch",
            "Flood Advisory": "flood_advisory",
        }

        for feature in features:
            event = feature.get("properties", {}).get("event", "")
            for key, value in alert_priority.items():
                if key.lower() in event.lower():
                    return value

        return "none"

    except Exception:
        return "none"


def _get_forecast(lat: float, lng: float) -> dict[str, Any]:
    """
    Gets hourly forecast from NWS for a lat/lng.
    Step 1: GET /points/{lat},{lng} → get forecast URLs
    Step 2: GET forecastHourly URL → get hourly periods
    """
    try:
        # Step 1 — get grid info
        points_data = _get(f"{NWS_BASE}/points/{lat},{lng}")
        properties = points_data.get("properties", {})
        hourly_url = properties.get("forecastHourly")
        forecast_url = properties.get("forecast")

        if not hourly_url or not forecast_url:
            return {}

        # Step 2 — get hourly forecast
        hourly_data = _get(hourly_url)
        periods = hourly_data.get("properties", {}).get("periods", [])

        # Sum rain probability and extract summary from next 6 hours
        rain_next_6hr = 0.0
        storm_probability = 0.0
        forecast_summary = "No summary available."

        for i, period in enumerate(periods[:6]):
            prob = period.get("probabilityOfPrecipitation", {}).get("value") or 0
            storm_probability = max(storm_probability, prob / 100)

        # Get daily forecast summary
        daily_data = _get(forecast_url)
        daily_periods = daily_data.get("properties", {}).get("periods", [])
        if daily_periods:
            forecast_summary = daily_periods[0].get("detailedForecast", "No summary available.")

        # Estimate rain from quantitative precipitation if available
        # NWS hourly gives probabilityOfPrecipitation not exact inches
        # so we estimate: high prob periods contribute ~0.1in each
        rain_next_6hr = sum(
            0.1 for p in periods[:6]
            if (p.get("probabilityOfPrecipitation", {}).get("value") or 0) > 50
        )
        rain_forecast_inches = sum(
            0.1 for p in periods[:24]
            if (p.get("probabilityOfPrecipitation", {}).get("value") or 0) > 50
        )

        return {
            "rain_forecast_inches": round(rain_forecast_inches, 1),
            "rain_next_6hr_inches": round(rain_next_6hr, 1),
            "storm_probability": round(storm_probability, 2),
            "forecast_summary": forecast_summary,
        }

    except Exception as e:
        return {}


def get_weather_context(lat: float, lng: float) -> dict[str, Any]:
    """
    Return weather forecast and alert context for a lat/lng location.
    Calls real NWS API endpoints.
    Falls back to defaults on any error.
    """
    try:
        alert = _get_active_alerts(lat, lng)
        forecast = _get_forecast(lat, lng)

        return {
            "weather_alert": alert,
            "rain_forecast_inches": forecast.get("rain_forecast_inches", 0.0),
            "rain_next_6hr_inches": forecast.get("rain_next_6hr_inches", 0.0),
            "storm_probability": forecast.get("storm_probability", 0.0),
            "forecast_summary": forecast.get("forecast_summary", "No forecast available."),
        }

    except Exception as e:
        print(f"[weather_service] Failed to fetch weather for ({lat}, {lng}): {e}")
        return _DEFAULT_WEATHER.copy()