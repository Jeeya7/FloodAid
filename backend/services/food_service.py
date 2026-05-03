# food_service.py
# Fetches food-assistance resources near a location.
# In production, replace the placeholder URL with a real API such as:
#   - Food Pantries API  (https://www.foodpantries.org)
#   - USDA SNAP retailer locator
#   - 211 API            (https://api.211.org)

from typing import Any

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# TODO: Replace with the real food-resource API endpoint when available
FOOD_API_URL = "https://xyz.example.com/food"

_TIMEOUT = 10  # seconds


# ── Mock data ─────────────────────────────────────────────────────────────────
# Returned when the real API is unreachable.
# Source is clearly labelled "mock_food_api" so callers know it is not live data.

_MOCK_FOOD_RESOURCES = [
    {
        "id": "food-001",
        "name": "Newport Community Food Pantry",
        "type": "pantry",
        "lat": 44.6368,
        "lng": -124.0535,
        "address": "432 NW Coast St, Newport, OR 97365",
        "distance_miles": 0.4,
        "status": "open",
        "phone": "541-555-0101",
        "notes": "Open Mon–Fri 9am–5pm. Emergency distributions available during flood events.",
    },
    {
        "id": "food-002",
        "name": "Lincoln County Meal Site",
        "type": "meal_site",
        "lat": 44.6412,
        "lng": -124.0510,
        "address": "118 SE Benton St, Newport, OR 97365",
        "distance_miles": 0.7,
        "status": "open",
        "phone": "541-555-0202",
        "notes": "Hot meals served daily. Disaster relief supplies available on request.",
    },
    {
        "id": "food-003",
        "name": "Oregon Coast Emergency Food Bank",
        "type": "food_bank",
        "lat": 44.6290,
        "lng": -124.0600,
        "address": "750 SW Coos Ave, Newport, OR 97365",
        "distance_miles": 1.2,
        "status": "open",
        "phone": "541-555-0303",
        "notes": "Regional food bank. Drive-through distribution during emergencies.",
    },
]


# ── Normalizer ────────────────────────────────────────────────────────────────

def _normalize_resource(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one raw API item to the standard food resource schema."""
    valid_types = {"food_bank", "meal_site", "pantry"}
    raw_type = str(raw.get("type", "")).lower().replace(" ", "_")

    return {
        "id":             str(raw.get("id", "unknown")),
        "name":           str(raw.get("name", "Unknown Food Resource")),
        "type":           raw_type if raw_type in valid_types else "unknown",
        "lat":            float(raw.get("lat", 0.0)),
        "lng":            float(raw.get("lng", 0.0)),
        "address":        str(raw.get("address", "")),
        "distance_miles": float(raw.get("distance_miles", 0.0)),
        "status":         raw.get("status") if raw.get("status") in ("open", "closed") else "unknown",
        "phone":          str(raw.get("phone", "")),
        "notes":          str(raw.get("notes", "")),
    }


# ── Public function ───────────────────────────────────────────────────────────

def get_food_resources(
    lat: float,
    lng: float,
    radius_miles: float = 10,
) -> dict[str, Any]:
    """
    Return food-assistance resources near the given coordinates.

    In production this calls:
      GET FOOD_API_URL?lat=<lat>&lng=<lng>&radius=<radius_miles>

    Falls back to mock data if the request fails or requests is unavailable.
    """
    if not _REQUESTS_AVAILABLE:
        return {
            "source": "mock_food_api",
            "resources": _MOCK_FOOD_RESOURCES,
            "error": "requests library not installed; using mock data.",
        }

    try:
        response = requests.get(
            FOOD_API_URL,
            params={"lat": lat, "lng": lng, "radius": radius_miles},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        # TODO: Adjust the key below to match the real API's response envelope
        raw_list: list[dict] = response.json().get("resources", response.json())
        return {
            "source": "food_api",
            "resources": [_normalize_resource(r) for r in raw_list],
        }

    except Exception as exc:
        # Placeholder endpoint is not live yet — return labelled mock data
        return {
            "source": "mock_food_api",
            "resources": _MOCK_FOOD_RESOURCES,
            "error": str(exc),
        }
