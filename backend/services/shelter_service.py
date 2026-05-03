# shelter_service.py
# Fetches emergency shelter resources near a location.
# In production, replace the placeholder URL with a real API such as:
#   - FEMA Disaster Recovery Centers API (https://www.fema.gov/api)
#   - American Red Cross shelter finder  (https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html)
#   - 211 API                            (https://api.211.org)

from typing import Any

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# TODO: Replace with the real shelter API endpoint when available
SHELTER_API_URL = "https://xyz.example.com/shelters"

_TIMEOUT = 10  # seconds


# ── Mock data ─────────────────────────────────────────────────────────────────
# Returned when the real API is unreachable.
# Source is clearly labelled "mock_shelter_api" so callers know it is not live data.

_MOCK_SHELTER_RESOURCES = [
    {
        "id": "shelter-001",
        "name": "Newport High School Evacuation Shelter",
        "type": "evacuation_shelter",
        "lat": 44.6350,
        "lng": -124.0545,
        "address": "322 NE Fogarty St, Newport, OR 97365",
        "distance_miles": 0.5,
        "status": "open",
        "capacity": 350,
        "phone": "541-555-0501",
        "notes": "ADA accessible. Pets allowed in designated area. Activated by Lincoln County Emergency Management.",
    },
    {
        "id": "shelter-002",
        "name": "Lincoln Events Center Emergency Shelter",
        "type": "evacuation_shelter",
        "lat": 44.6445,
        "lng": -124.0500,
        "address": "33 NE 2nd St, Newport, OR 97365",
        "distance_miles": 0.8,
        "status": "open",
        "capacity": 500,
        "phone": "541-555-0502",
        "notes": "Large-capacity venue. Red Cross managed. Cots, meals, and medical station available.",
    },
    {
        "id": "shelter-003",
        "name": "Coastal Community Warming Center",
        "type": "warming_center",
        "lat": 44.6300,
        "lng": -124.0580,
        "address": "612 SE Marine Science Dr, Newport, OR 97365",
        "distance_miles": 1.1,
        "status": "open",
        "capacity": 80,
        "phone": "541-555-0503",
        "notes": "Overnight warming center. No pets. Open 6pm–8am during active weather events.",
    },
    {
        "id": "shelter-004",
        "name": "Bayfront Temporary Shelter",
        "type": "temporary_shelter",
        "lat": 44.6275,
        "lng": -124.0610,
        "address": "150 SW Bay Blvd, Newport, OR 97365",
        "distance_miles": 1.5,
        "status": "closed",
        "capacity": 120,
        "phone": "541-555-0504",
        "notes": "Currently closed. Will open if county issues a flood emergency declaration.",
    },
]


# ── Normalizer ────────────────────────────────────────────────────────────────

def _normalize_resource(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one raw API item to the standard shelter resource schema."""
    valid_types = {"evacuation_shelter", "warming_center", "temporary_shelter"}
    raw_type = str(raw.get("type", "")).lower().replace(" ", "_")

    # capacity can be None/null when not reported by the API
    raw_capacity = raw.get("capacity")
    capacity = int(raw_capacity) if raw_capacity is not None else None

    return {
        "id":             str(raw.get("id", "unknown")),
        "name":           str(raw.get("name", "Unknown Shelter")),
        "type":           raw_type if raw_type in valid_types else "unknown",
        "lat":            float(raw.get("lat", 0.0)),
        "lng":            float(raw.get("lng", 0.0)),
        "address":        str(raw.get("address", "")),
        "distance_miles": float(raw.get("distance_miles", 0.0)),
        "status":         raw.get("status") if raw.get("status") in ("open", "closed") else "unknown",
        "capacity":       capacity,
        "phone":          str(raw.get("phone", "")),
        "notes":          str(raw.get("notes", "")),
    }


# ── Public function ───────────────────────────────────────────────────────────

def get_shelters(
    lat: float,
    lng: float,
    radius_miles: float = 10,
) -> dict[str, Any]:
    """
    Return emergency shelter resources near the given coordinates.

    In production this calls:
      GET SHELTER_API_URL?lat=<lat>&lng=<lng>&radius=<radius_miles>

    Falls back to mock data if the request fails or requests is unavailable.
    """
    if not _REQUESTS_AVAILABLE:
        return {
            "source": "mock_shelter_api",
            "resources": _MOCK_SHELTER_RESOURCES,
            "error": "requests library not installed; using mock data.",
        }

    try:
        response = requests.get(
            SHELTER_API_URL,
            params={"lat": lat, "lng": lng, "radius": radius_miles},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        # TODO: Adjust the key below to match the real API's response envelope
        raw_list: list[dict] = response.json().get("resources", response.json())
        return {
            "source": "shelter_api",
            "resources": [_normalize_resource(r) for r in raw_list],
        }

    except Exception as exc:
        # Placeholder endpoint is not live yet — return labelled mock data
        return {
            "source": "mock_shelter_api",
            "resources": _MOCK_SHELTER_RESOURCES,
            "error": str(exc),
        }
