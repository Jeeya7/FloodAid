import requests
from typing import Any

def get_location(city: str, state: str) -> dict[str, Any]:
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    
    params = {
        "address": f"{city}, {state}",
        "benchmark": "2020",
        "format": "json"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    coords = data["result"]["addressMatches"][0]["coordinates"]

    return {
        "lat": coords["y"],
        "lng": coords["x"],
        "city": city,
        "state": state,
    }