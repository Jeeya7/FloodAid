# weather_service.py
# Calls the real National Weather Service (NWS) API.
# https://api.weather.gov/
# No API key needed — just requires a User-Agent header.

import json
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

NWS_BASE = "https://api.weather.gov"
_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@beaverhacks.com)",
    "Accept": "application/geo+json",
}
_DEFAULT_WEATHER: dict[str, Any] = {
    "weather_alert": "none",
    "rain_forecast_inches": 0.0,
    "rain_next_6hr_inches": 0.0,
    "storm_probability": 0.0,
    "forecast_summary": "No weather data available for this location.",
}

# 5s to connect, 20s to read — NWS forecast URLs can be slow
_TIMEOUT = (5, 20)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)
    retry = Retry(
        total=3,
        backoff_factor=0.5,          # 0s → 0.5s → 1s between retries
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


def get_weather_context(lat: float, lng: float) -> dict[str, Any]:
    """
    Fetches real NWS weather data for a lat/lng.
    Called by the agent with the location it already has.
    Returns a dict with the same keys as the old mock data.
    """
    try:
        # Step 1 — get alerts
        alerts_data = _get(f"{NWS_BASE}/alerts/active?point={lat},{lng}")
        features = alerts_data.get("features", [])
        priority = {
            "flash flood warning": "flood_warning",
            "flood warning":       "flood_warning",
            "flash flood watch":   "flood_watch",
            "flood watch":         "flood_watch",
            "flood advisory":      "flood_advisory",
        }
        weather_alert = "none"
        for feature in features:
            event = feature.get("properties", {}).get("event", "").lower()
            for key, value in priority.items():
                if key in event:
                    weather_alert = value
                    break

        # Step 2 — get grid URLs for this location
        points = _get(f"{NWS_BASE}/points/{lat},{lng}")
        props = points.get("properties", {})
        hourly_url = props.get("forecastHourly")
        forecast_url = props.get("forecast")

        # Step 3 — hourly rain probabilities
        storm_probability = 0.0
        rain_next_6hr_inches = 0.0
        rain_forecast_inches = 0.0
        if hourly_url:
            hourly = _get(hourly_url)
            periods = hourly.get("properties", {}).get("periods", [])
            for i, period in enumerate(periods[:24]):
                prob = (period.get("probabilityOfPrecipitation") or {}).get("value") or 0
                if i < 6:
                    storm_probability = max(storm_probability, prob / 100)
                if prob > 50:
                    rain_next_6hr_inches += 0.1
                if prob > 50:
                    rain_forecast_inches += 0.1

        # Step 4 — plain language summary
        forecast_summary = "No summary available."
        if forecast_url:
            daily = _get(forecast_url)
            daily_periods = daily.get("properties", {}).get("periods", [])
            if daily_periods:
                forecast_summary = daily_periods[0].get("detailedForecast", "No summary available.")

        return {
            "weather_alert":        weather_alert,
            "rain_forecast_inches": round(rain_forecast_inches, 1),
            "rain_next_6hr_inches": round(rain_next_6hr_inches, 1),
            "storm_probability":    round(storm_probability, 2),
            "forecast_summary":     forecast_summary,
        }

    except Exception as e:
        print(f"[weather_service] Failed for ({lat}, {lng}): {e}")
        return _DEFAULT_WEATHER.copy()