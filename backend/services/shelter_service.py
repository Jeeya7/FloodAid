# shelter_service.py
# Fetches emergency shelter resources using the Red Cross Open Shelter API.
# https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html

import urllib.request
import urllib.parse
import json
import math
from typing import Any

# Red Cross shelter API — no key required
REDCROSS_API_URL = "https://api.redcross.org/v2/shelters"

_TIMEOUT = 10

_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@beaverhacks.com)",
    "Accept": "application/json",
}


def _distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in miles."""
    R = 3958.8
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _normalize(raw: dict[str, Any], user_lat: float, user_lng: float) -> dict[str, Any]:
    shelter_lat = float(raw.get("latitude", 0.0))
    shelter_lng = float(raw.get("longitude", 0.0))

    return {
        "id":             str(raw.get("id", "unknown")),
        "name":           str(raw.get("name", "Unknown Shelter")),
        "type":           "evacuation_shelter",
        "lat":            shelter_lat,
        "lng":            shelter_lng,
        "address":        str(raw.get("address", "")),
        "distance_miles": round(_distance_miles(user_lat, user_lng, shelter_lat, shelter_lng), 1),
        "status":         "open" if raw.get("isOpen", False) else "closed",
        "capacity":       raw.get("capacity"),
        "phone":          str(raw.get("phone", "")),
        "notes":          str(raw.get("notes", "")),
    }


def _try_redcross(lat: float, lng: float, radius_miles: float) -> list[dict[str, Any]]:
    """Try Red Cross API."""
    params = urllib.parse.urlencode({
        "lat":    lat,
        "lng":    lng,
        "radius": radius_miles,
    })
    url = REDCROSS_API_URL + "?" + params
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw_list = data.get("shelters", data.get("results", []))
    return [_normalize(r, lat, lng) for r in raw_list]


def _try_fema(lat: float, lng: float, radius_miles: float) -> list[dict[str, Any]]:
    """Try FEMA Disaster Shelter API."""
    deg_offset = radius_miles / 69.0
    filter_str = (
        f"latitude gt {round(lat - deg_offset, 4)} and "
        f"latitude lt {round(lat + deg_offset, 4)} and "
        f"longitude gt {round(lng - deg_offset, 4)} and "
        f"longitude lt {round(lng + deg_offset, 4)}"
    )
    params = urllib.parse.urlencode({
        "$filter":  filter_str,
        "$orderby": "shelterName asc",
        "$top":     "20",
        "$format":  "json",
    })
    url = "https://www.fema.gov/api/open/v2/disasterShelters?" + params
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw_list = data.get("disasterShelters", [])

    def normalize_fema(raw: dict) -> dict:
        shelter_lat = float(raw.get("latitude", 0.0))
        shelter_lng = float(raw.get("longitude", 0.0))
        return {
            "id":             str(raw.get("id", "unknown")),
            "name":           str(raw.get("shelterName", "Unknown Shelter")),
            "type":           "evacuation_shelter",
            "lat":            shelter_lat,
            "lng":            shelter_lng,
            "address":        f"{raw.get('address1', '')} {raw.get('city', '')} {raw.get('state', '')} {raw.get('zip', '')}".strip(),
            "distance_miles": round(_distance_miles(lat, lng, shelter_lat, shelter_lng), 1),
            "status":         "open" if raw.get("shelterStatus", "").lower() == "open" else "closed",
            "capacity":       raw.get("maximumCapacity"),
            "phone":          str(raw.get("phone", "")),
            "notes":          str(raw.get("specialNeeds", "")),
        }

    return [normalize_fema(r) for r in raw_list]


def get_shelters(
    lat: float,
    lng: float,
    radius_miles: float = 25,
) -> dict[str, Any]:
    """
    Return emergency shelter resources near the given coordinates.
    Tries Red Cross API first, falls back to FEMA API.
    Called by the agent with the lat/lng it already has.
    """
    # Try Red Cross first
    try:
        resources = _try_redcross(lat, lng, radius_miles)
        resources.sort(key=lambda x: x["distance_miles"])
        return {
            "source":    "redcross_api",
            "count":     len(resources),
            "resources": resources,
        }
    except Exception as e:
        print(f"[shelter_service] Red Cross API failed: {e} — trying FEMA")

    # Fall back to FEMA
    try:
        resources = _try_fema(lat, lng, radius_miles)
        resources.sort(key=lambda x: x["distance_miles"])
        return {
            "source":    "fema_api",
            "count":     len(resources),
            "resources": resources,
        }
    except Exception as e:
        print(f"[shelter_service] FEMA API also failed: {e}")
        raise RuntimeError(f"All shelter APIs failed: {e}")


if __name__ == "__main__":
    lat, lng = 45.8918, -123.9615
    print(f"Testing shelters for Cannon Beach, OR ({lat}, {lng})\n")

    result = get_shelters(lat, lng, radius_miles=25)
    print(json.dumps(result, indent=2))

    with open("cannon_beach_shelters.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFound {result['count']} shelters. Saved to cannon_beach_shelters.json")