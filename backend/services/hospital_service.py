# hospital_service.py
# Fetches hospital and urgent-care resources near a location.
# In production, replace the placeholder URL with a real API such as:
#   - CMS Hospital Compare API (https://data.cms.gov)
#   - Healthgrades API
#   - 211 API                  (https://api.211.org)

from typing import Any

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# TODO: Replace with the real hospital-resource API endpoint when available
HOSPITAL_API_URL = "https://xyz.example.com/hospitals"

_TIMEOUT = 10  # seconds


# ── Mock data ─────────────────────────────────────────────────────────────────
# Returned when the real API is unreachable.
# Source is clearly labelled "mock_hospital_api" so callers know it is not live data.

_MOCK_HOSPITAL_RESOURCES = [
    {
        "id": "hosp-001",
        "name": "Samaritan Pacific Communities Hospital",
        "type": "hospital",
        "lat": 44.6380,
        "lng": -124.0520,
        "address": "930 SW Abbey St, Newport, OR 97365",
        "distance_miles": 0.3,
        "status": "open",
        "phone": "541-265-2244",
        "emergency_services": True,
        "notes": "Full emergency department. Flood surge capacity protocols in effect.",
    },
    {
        "id": "hosp-002",
        "name": "Newport Urgent Care Center",
        "type": "urgent_care",
        "lat": 44.6420,
        "lng": -124.0490,
        "address": "154 NE 10th St, Newport, OR 97365",
        "distance_miles": 0.6,
        "status": "open",
        "phone": "541-555-0410",
        "emergency_services": False,
        "notes": "Walk-in clinic. Not equipped for major trauma during disaster events.",
    },
    {
        "id": "hosp-003",
        "name": "Lincoln County Health Clinic",
        "type": "clinic",
        "lat": 44.6310,
        "lng": -124.0570,
        "address": "28 SW Benton St, Newport, OR 97365",
        "distance_miles": 0.9,
        "status": "open",
        "phone": "541-555-0420",
        "emergency_services": False,
        "notes": "Primary care and referrals. Extended hours during declared emergencies.",
    },
]


# ── Normalizer ────────────────────────────────────────────────────────────────

def _normalize_resource(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one raw API item to the standard hospital resource schema."""
    valid_types = {"hospital", "urgent_care", "clinic"}
    raw_type = str(raw.get("type", "")).lower().replace(" ", "_")

    return {
        "id":                 str(raw.get("id", "unknown")),
        "name":               str(raw.get("name", "Unknown Medical Facility")),
        "type":               raw_type if raw_type in valid_types else "unknown",
        "lat":                float(raw.get("lat", 0.0)),
        "lng":                float(raw.get("lng", 0.0)),
        "address":            str(raw.get("address", "")),
        "distance_miles":     float(raw.get("distance_miles", 0.0)),
        "status":             raw.get("status") if raw.get("status") in ("open", "closed") else "unknown",
        "phone":              str(raw.get("phone", "")),
        "emergency_services": bool(raw.get("emergency_services", False)),
        "notes":              str(raw.get("notes", "")),
    }


# ── Public function ───────────────────────────────────────────────────────────

def get_hospitals(
    lat: float,
    lng: float,
    radius_miles: float = 10,
) -> dict[str, Any]:
    """
    Return hospital and medical resources near the given coordinates.

    In production this calls:
      GET HOSPITAL_API_URL?lat=<lat>&lng=<lng>&radius=<radius_miles>

    Falls back to mock data if the request fails or requests is unavailable.
    """
    if not _REQUESTS_AVAILABLE:
        return {
            "source": "mock_hospital_api",
            "resources": _MOCK_HOSPITAL_RESOURCES,
            "error": "requests library not installed; using mock data.",
        }

    try:
        response = requests.get(
            HOSPITAL_API_URL,
            params={"lat": lat, "lng": lng, "radius": radius_miles},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        # TODO: Adjust the key below to match the real API's response envelope
        raw_list: list[dict] = response.json().get("resources", response.json())
        return {
            "source": "hospital_api",
            "resources": [_normalize_resource(r) for r in raw_list],
        }

    except Exception as exc:
        # Placeholder endpoint is not live yet — return labelled mock data
        return {
            "source": "mock_hospital_api",
            "resources": _MOCK_HOSPITAL_RESOURCES,
            "error": str(exc),
        }
