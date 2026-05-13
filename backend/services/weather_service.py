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

# returned when the API call fails so the agent still gets something
_DEFAULT_WEATHER: dict[str, Any] = {
    "weather_alert":        "none",
    "rain_forecast_inches": 0.0,
    "rain_next_6hr_inches": 0.0,
    "storm_probability":    0.0,
    "forecast_summary":     "No weather data available for this location.",
}

# 5s to connect, 20s to read — NWS forecast URLs can be slow
_TIMEOUT = (5, 20)


def _make_session() -> requests.Session:
    # same retry setup as usgs_service — handles temporary NWS outages gracefully
    session = requests.Session()
    session.headers.update(_HEADERS)

    retry = Retry(
        total=3,
        backoff_factor=0.5,                    # waits 0.5s, 1s, 2s between retries
        status_forcelist={500, 502, 503, 504}, # only retry on server errors
        allowed_methods={"GET"},
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# single shared session reused across all calls
_SESSION = _make_session()


def _get(url: str) -> dict[str, Any]:
    # simple wrapper that raises if we get a non-200 response
    resp = _SESSION.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_weather_context(lat: float, lng: float) -> dict[str, Any]:
    """
    Fetches real NWS weather data for a lat/lng.
    Called by the risk_region_agent with the gauge station's coordinates.
    Returns a dict the weather_risk_agent uses to assess flood danger.
    """
    try:
        # step 1 — check for active flood alerts at this location
        # NWS alerts tell us if there's already a flood warning or watch in effect
        alerts_data = _get(f"{NWS_BASE}/alerts/active?point={lat},{lng}")
        features = alerts_data.get("features", [])

        # map NWS alert names to our simplified alert levels
        # ordered from most to least severe
        priority = {
            "flash flood warning": "flood_warning",
            "flood warning":       "flood_warning",
            "flash flood watch":   "flood_watch",
            "flood watch":         "flood_watch",
            "flood advisory":      "flood_advisory",
        }

        # find the most severe active alert
        weather_alert = "none"
        for feature in features:
            event = feature.get("properties", {}).get("event", "").lower()
            for key, value in priority.items():
                if key in event:
                    weather_alert = value
                    break

        # step 2 — get the NWS grid URLs for this location
        # NWS works by first looking up which grid cell covers your lat/lng
        # then you use that grid's URLs to get the actual forecast
        points = _get(f"{NWS_BASE}/points/{lat},{lng}")
        props = points.get("properties", {})
        hourly_url   = props.get("forecastHourly")  # hour by hour forecast
        forecast_url = props.get("forecast")         # plain language daily forecast

        # step 3 — parse hourly forecast for rain probabilities
        storm_probability    = 0.0
        rain_next_6hr_inches = 0.0
        rain_forecast_inches = 0.0

        if hourly_url:
            hourly  = _get(hourly_url)
            periods = hourly.get("properties", {}).get("periods", [])

            # look at the next 24 hours of hourly forecasts
            for i, period in enumerate(periods[:24]):
                prob = (period.get("probabilityOfPrecipitation") or {}).get("value") or 0

                # use the first 6 hours for the near-term storm probability
                if i < 6:
                    storm_probability = max(storm_probability, prob / 100)

                # estimate rainfall by counting high-probability hours
                # not perfectly accurate but good enough for risk assessment
                if prob > 50:
                    rain_next_6hr_inches += 0.1
                if prob > 50:
                    rain_forecast_inches += 0.1

        # step 4 — get the plain language forecast summary
        # this is what the weather_risk_agent reads to understand the situation
        forecast_summary = "No summary available."
        if forecast_url:
            daily        = _get(forecast_url)
            daily_periods = daily.get("properties", {}).get("periods", [])
            if daily_periods:
                # just grab the first period's detailed forecast
                forecast_summary = daily_periods[0].get("detailedForecast", "No summary available.")

        return {
            "weather_alert":        weather_alert,
            "rain_forecast_inches": round(rain_forecast_inches, 1),
            "rain_next_6hr_inches": round(rain_next_6hr_inches, 1),
            "storm_probability":    round(storm_probability, 2),
            "forecast_summary":     forecast_summary,
        }

    except Exception as e:
        # if anything fails return the default so the agent still has data to work with
        print(f"[weather_service] Failed for ({lat}, {lng}): {e}")
        return _DEFAULT_WEATHER.copy()