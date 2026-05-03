# shelter_service.py
# Fetches emergency shelter resources using OpenStreetMap Overpass API.
# Uses emergency:social_facility=shelter — the correct OSM tag for
# buildings designated as emergency shelters (schools, community centers, etc.)

import urllib.request
import urllib.parse
import json
import math
from typing import Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_TIMEOUT = 15

_HEADERS = {
    "User-Agent": "FloodAid/1.0 (floodaid@beaverhacks.com)",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _normalize(element: dict[str, Any], user_lat: float, user_lng: float) -> dict[str, Any]:
    tags = element.get("tags", {})

    if element.get("type") == "node":
        shelter_lat = float(element.get("lat", 0.0))
        shelter_lng = float(element.get("lon", 0.0))
    else:
        center = element.get("center", {})
        shelter_lat = float(center.get("lat", 0.0))
        shelter_lng = float(center.get("lon", 0.0))

    address = " ".join(filter(None, [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:city", ""),
        tags.get("addr:state", ""),
        tags.get("addr:postcode", ""),
    ])).strip()

    name = (
        tags.get("name")
        or tags.get("official_name")
        or tags.get("amenity", "Unknown Shelter").replace("_", " ").title()
    )

    raw_capacity = tags.get("capacity")
    capacity = int(raw_capacity) if raw_capacity is not None else None

    # Determine shelter type from OSM tags
    amenity = tags.get("amenity", "")
    building = tags.get("building", "")
    if "school" in amenity or "school" in building:
        shelter_type = "evacuation_shelter"
    elif "community" in amenity or "community" in building:
        shelter_type = "evacuation_shelter"
    elif "stadium" in amenity or "stadium" in building:
        shelter_type = "evacuation_shelter"
    else:
        shelter_type = "evacuation_shelter"

    return {
        "id":             str(element.get("id", "unknown")),
        "name":           name,
        "type":           shelter_type,
        "lat":            shelter_lat,
        "lng":            shelter_lng,
        "address":        address,
        "distance_miles": round(_distance_miles(user_lat, user_lng, shelter_lat, shelter_lng), 1),
        "status":         "open",
        "capacity":       capacity,
        "phone":          tags.get("phone", tags.get("contact:phone", "")),
        "notes":          tags.get("description", tags.get("emergency", "")),
    }


def get_shelters(
    lat: float,
    lng: float,
    radius_miles: float = 10,
) -> dict[str, Any]:
    """
    Return emergency shelter resources near the given coordinates.
    Uses OSM emergency:social_facility=shelter tag plus common
    shelter-eligible buildings (schools, community centers, stadiums).
    Works for any lat/lng in the world.
    """
    radius_meters = int(radius_miles * 1609.34)

    query = f"""
[out:json][timeout:15];
(
  node["emergency:social_facility"="shelter"](around:{radius_meters},{lat},{lng});
  way["emergency:social_facility"="shelter"](around:{radius_meters},{lat},{lng});
  node["social_facility"="shelter"](around:{radius_meters},{lat},{lng});
  way["social_facility"="shelter"](around:{radius_meters},{lat},{lng});
  node["amenity"="community_centre"](around:{radius_meters},{lat},{lng});
  way["amenity"="community_centre"](around:{radius_meters},{lat},{lng});
  node["amenity"="school"](around:{radius_meters},{lat},{lng});
  way["amenity"="school"](around:{radius_meters},{lat},{lng});
  node["leisure"="stadium"](around:{radius_meters},{lat},{lng});
  way["leisure"="stadium"](around:{radius_meters},{lat},{lng});
);
out center tags;
"""

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, headers=_HEADERS)

    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    elements = result.get("elements", [])
    resources = [_normalize(e, lat, lng) for e in elements]
    resources.sort(key=lambda x: x["distance_miles"])

    return {
        "source":    "openstreetmap",
        "count":     len(resources),
        "resources": resources[:20],  # cap at 20 nearest
    }


if __name__ == "__main__":
    import sys

    # Default: Cook County MN — has active flood advisory right now
    lat, lng = 48.0, -91.5
    label = "Cook County, MN"

    if len(sys.argv) == 3:
        lat, lng = float(sys.argv[1]), float(sys.argv[2])
        label = f"({lat}, {lng})"

    print(f"Testing shelters for {label}\n")
    result = get_shelters(lat, lng, radius_miles=25)
    print(json.dumps(result, indent=2))

    with open("shelters_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFound {result['count']} shelters. Saved to shelters_output.json")