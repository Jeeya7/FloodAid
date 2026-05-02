import requests
from typing import Any


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