# food_service.py
# Fetches food-assistance resources near a location using Google Places.
# Falls back to labelled mock data if API fails or returns no usable results.

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


# Small offsets (in degrees) used to scatter mock resources around the request point.
# ~0.01° lat ≈ 0.7 mi,  ~0.01° lng ≈ 0.5 mi at mid-latitudes.
_MOCK_OFFSETS = [
    {"dlat":  0.004, "dlng":  0.006},  # ~0.4 mi NE
    {"dlat":  0.007, "dlng": -0.005},  # ~0.6 mi NW
    {"dlat": -0.011, "dlng":  0.003},  # ~0.8 mi S
]

_MOCK_FOOD_TEMPLATES = [
    {
        "id": "food-001",
        "name": "Community Food Pantry",
        "type": "pantry",
        "status": "open",
        "opening_hours": {"open_now": True},
        "phone": "541-555-0101",
        "notes": "Mock data – Google Places key not configured.",
    },
    {
        "id": "food-002",
        "name": "County Emergency Meal Site",
        "type": "meal_site",
        "status": "open",
        "opening_hours": {"open_now": True},
        "phone": "541-555-0202",
        "notes": "Mock data – Google Places key not configured.",
    },
    {
        "id": "food-003",
        "name": "Regional Emergency Food Bank",
        "type": "food_bank",
        "status": "open",
        "opening_hours": {"open_now": True},
        "phone": "541-555-0303",
        "notes": "Mock data – Google Places key not configured.",
    },
]


def _build_mock_resources(lat: float, lng: float) -> list[dict]:
    """Generate mock food resources scattered around the requested location."""
    resources = []
    for template, offset in zip(_MOCK_FOOD_TEMPLATES, _MOCK_OFFSETS):
        r_lat = round(lat + offset["dlat"], 6)
        r_lng = round(lng + offset["dlng"], 6)
        resources.append({
            **template,
            "lat":            r_lat,
            "lng":            r_lng,
            "address":        f"Near {round(lat, 3)}, {round(lng, 3)}",
            "distance_miles": round(_distance_miles(lat, lng, r_lat, r_lng), 2),
        })
    return resources


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


def _is_food_assistance_place(place: dict[str, Any]) -> bool:
    """
    Keep real emergency food resources.
    Remove grocery stores, gas stations, restaurants, and random food businesses.
    """

    name = place.get("name", "").lower()
    types = place.get("types", [])

    strong_keywords = [
        "food bank",
        "food pantry",
        "food share",
        "food distribution",
        "meal site",
        "basic needs",
    ]

    reject_types = {
        "grocery_or_supermarket",
        "convenience_store",
        "gas_station",
        "liquor_store",
        "bakery",
        "cafe",
        "restaurant",
    }

    if any(keyword in name for keyword in strong_keywords):
        return True

    if any(place_type in reject_types for place_type in types):
        return False

    return False


def _normalize_google_place(
    place: dict[str, Any],
    index: int,
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
        "id": f"food-{index:03}",
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


def _mock_response(lat: float, lng: float, reason: str) -> dict[str, Any]:
    """Return mock data placed near the requested coordinates."""
    return {
        "source": "mock_food_api",
        "using_mock_data": True,
        "resources": _build_mock_resources(lat, lng),
        "error": reason,
    }


def get_food_resources(
    lat: float,
    lng: float,
    radius_miles: float = 25,
) -> dict[str, Any]:
    """
    Return nearby food-assistance resources.

    Uses Google Places when usable results exist.
    Falls back to mock data when:
    - requests is unavailable
    - GOOGLE_PLACES_API_KEY is missing
    - Google API errors
    - Google returns no valid food assistance resources
    """

    if not _REQUESTS_AVAILABLE:
        return _mock_response(lat, lng, "requests library not installed")

    if not GOOGLE_PLACES_API_KEY:
        return _mock_response(lat, lng, "GOOGLE_PLACES_API_KEY missing from .env")

    try:
        radius_meters = int(min(radius_miles, 25) * 1609.34)

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

        if data.get("status") not in {"OK", "ZERO_RESULTS"}:
            return _mock_response(lat, lng, f"Google Places error: {data.get('status')}")

        raw_places = data.get("results", [])

        filtered_places = [
            place for place in raw_places if _is_food_assistance_place(place)
        ]

        if not filtered_places:
            return _mock_response(lat, lng, "Google Places returned no food assistance resources")

        resources = [
            _normalize_google_place(place, index, lat, lng)
            for index, place in enumerate(filtered_places, start=1)
        ]

        resources.sort(key=lambda item: item["distance_miles"])

        return {
            "source": "google_places",
            "using_mock_data": False,
            "resources": resources,
            "error": None,
        }

    except Exception as exc:
        return _mock_response(lat, lng, str(exc))