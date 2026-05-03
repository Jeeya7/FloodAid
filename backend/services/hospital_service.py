import urllib.request
import urllib.parse
import json
import math
from typing import Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@example.com)",
    "Content-Type": "application/x-www-form-urlencoded",
}

_DEFAULT_RESPONSE: dict[str, Any] = {
    "source": "overpass_api",
    "resources": [],
    "error": "No hospitals found near this location.",
}


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _query_overpass(query: str) -> dict[str, Any]:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize(element: dict, user_lat: float, user_lng: float) -> dict[str, Any]:
    tags = element.get("tags", {})

    if element.get("type") == "node":
        lat = element.get("lat", 0.0)
        lng = element.get("lon", 0.0)
    else:
        center = element.get("center", {})
        lat = center.get("lat", 0.0)
        lng = center.get("lon", 0.0)

    distance = _haversine_miles(user_lat, user_lng, lat, lng)

    amenity = tags.get("amenity", "hospital")
    if amenity == "hospital":
        facility_type = "hospital"
    elif amenity == "clinic":
        facility_type = "clinic"
    else:
        facility_type = "urgent_care"

    return {
        "id": str(element.get("id", "unknown")),
        "name": tags.get("name", "Unknown Medical Facility"),
        "type": facility_type,
        "lat": lat,
        "lng": lng,
        "address": tags.get("addr:full", f"{tags.get('addr:housenumber', '')} {tags.get('addr:street', '')}".strip()),
        "phone": tags.get("phone", tags.get("contact:phone", "")),
        "distance_miles": round(distance, 2),
        "status": "open",
        "emergency_services": tags.get("emergency", "") == "yes" or facility_type == "hospital",
        "notes": tags.get("description", ""),
    }


def get_hospitals(lat: float, lng: float, radius_miles: float = 10) -> dict[str, Any]:
    """
    Fetch hospitals near lat/lng from OpenStreetMap Overpass API.
    Called by the agent with coordinates from map_screen.dart.
    """
    radius_meters = int(radius_miles * 1609.34)

    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="hospital"](around:{radius_meters},{lat},{lng});
      way["amenity"="hospital"](around:{radius_meters},{lat},{lng});
      relation["amenity"="hospital"](around:{radius_meters},{lat},{lng});
      node["amenity"="clinic"](around:{radius_meters},{lat},{lng});
      way["amenity"="clinic"](around:{radius_meters},{lat},{lng});
      node["amenity"="urgent_care"](around:{radius_meters},{lat},{lng});
    );
    out center;
    """

    try:
        print(f"[hospital_service] Fetching hospitals near lat={lat}, lng={lng}, radius={radius_miles}mi")
        data = _query_overpass(query)
        elements = data.get("elements", [])

        if not elements:
            print("[hospital_service] No hospitals found")
            return _DEFAULT_RESPONSE.copy()

        resources = [_normalize(e, lat, lng) for e in elements]
        resources.sort(key=lambda x: x["distance_miles"])

        print(f"[hospital_service] Found {len(resources)} hospitals")
        return {
            "source": "overpass_api",
            "resources": resources,
        }

    except Exception as e:
        print(f"[hospital_service] Failed for ({lat}, {lng}): {e}")
        return {
            "source": "overpass_api",
            "resources": [],
            "error": str(e),
        }
    
