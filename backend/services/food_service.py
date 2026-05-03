# food_service.py
# Fetches food-assistance resources near a location using Google Places.

import math
import os
from typing import Any

from dotenv import load_dotenv

try:
    import requests

    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

_TIMEOUT = 10


def _extract_status(place: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract open/closed/unknown status from Google Places opening_hours."""

    opening_hours = place.get("opening_hours", {})
    open_now = opening_hours.get("open_now")

    if open_now is True:
        status = "open"
    elif open_now is False:
        status = "closed"
    else:
        status = "unknown"

    return status, {"open_now": open_now}


def _infer_resource_type(name: str) -> str:
    """Infer resource type from place name."""

    lowered = name.lower()

    if "food bank" in lowered:
        return "food_bank"

    if "meal" in lowered:
        return "meal_site"

    if "pantry" in lowered:
        return "pantry"

    if "food share" in lowered or "food distribution" in lowered:
        return "pantry"

    if "basic needs" in lowered:
        return "pantry"

    return "unknown"


def _distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two lat/lng points in miles."""
    radius_earth_miles = 3958.8

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius_earth_miles * c


def _normalize_google_place(
    place: dict[str, Any],
    user_lat: float,
    user_lng: float,
) -> dict[str, Any]:
    """Convert one Google Places result into your frontend-ready schema."""

    location = place.get("geometry", {}).get("location", {})

    place_lat = float(location.get("lat", 0.0))
    place_lng = float(location.get("lng", 0.0))

    name = place.get("name", "Unknown Food Resource")
    status, opening_hours = _extract_status(place)

    return {
        "id": place.get("place_id", name),
        "place_id": place.get("place_id", ""),
        "name": name,
        "type": _infer_resource_type(name),
        "lat": place_lat,
        "lng": place_lng,
        "address": place.get("vicinity", ""),
        "distance_miles": round(
            _distance_miles(user_lat, user_lng, place_lat, place_lng),
            2,
        ),
        "status": status,
        "opening_hours": opening_hours,
        "phone": place.get("international_phone_number", ""),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("user_ratings_total"),
        "business_status": place.get("business_status", "UNKNOWN"),
        "notes": "Google Places food assistance result.",
    }


def get_food_resources(
    lat: float,
    lng: float,
    radius_miles: float = 25,
) -> dict[str, Any]:
    """
    Return nearby food-assistance resources.

    Uses Google Places only.
    Returns an empty resource list when the API is unavailable or returns no matches.
    """

    if not _REQUESTS_AVAILABLE:
        print(f"[food_service] requests library not installed; returning empty result for lat={lat}, lng={lng}")
        return {"source": "google_places", "using_mock_data": False, "resources": [], "error": "requests library not installed"}

    if not GOOGLE_PLACES_API_KEY:
        print(f"[food_service] GOOGLE_PLACES_API_KEY missing; returning empty result for lat={lat}, lng={lng}")
        return {"source": "google_places", "using_mock_data": False, "resources": [], "error": "GOOGLE_PLACES_API_KEY missing from .env"}

    try:
        radius_meters = int(min(radius_miles, 25) * 1609.34)

        print(
            f"[food_service] Fetching food resources near lat={lat}, lng={lng}, radius={radius_miles}mi "
            f"({radius_meters}m)"
        )

        params = {
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "keyword": "food bank OR food pantry OR food share OR food distribution",
            "key": GOOGLE_PLACES_API_KEY,
        }

        response = requests.get(
            GOOGLE_PLACES_URL,
            params=params,
            timeout=_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()

        print(f"[food_service] Google Places status={data.get('status')}")

        if data.get("status") not in {"OK", "ZERO_RESULTS"}:
            return {
                "source": "google_places",
                "using_mock_data": False,
                "resources": [],
                "error": f"Google Places error: {data.get('status')}",
            }

        raw_places = data.get("results", [])
        print(f"[food_service] Google Places returned {len(raw_places)} raw results")

        if raw_places:
            preview = [place.get("name", "") for place in raw_places[:5]]
            print(f"[food_service] Raw place preview: {preview}")

        filtered_places = raw_places
        print(f"[food_service] Accepted {len(filtered_places)} of {len(raw_places)} raw results")

        if not filtered_places:
            print("[food_service] No food-assistance results from Google Places")
            return {
                "source": "google_places",
                "using_mock_data": False,
                "resources": [],
                "error": "Google Places returned no food assistance resources",
            }

        resources = [
            _normalize_google_place(place, lat, lng)
            for place in filtered_places
        ]

        resources.sort(key=lambda item: item["distance_miles"])

        print(f"[food_service] Returning {len(resources)} food resources from Google Places")

        return {
            "source": "google_places",
            "using_mock_data": False,
            "resources": resources,
            "error": None,
        }

    except Exception as exc:
        print(f"[food_service] Google Places fetch failed for lat={lat}, lng={lng}: {exc}")
        return {
            "source": "google_places",
            "using_mock_data": False,
            "resources": [],
            "error": str(exc),
        }