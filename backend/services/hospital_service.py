import urllib.request
import urllib.parse
import json
import math
import os
from typing import Any

_DEFAULT_RESPONSE: dict[str, Any] = {
    "source": "google_places",
    "resources": [],
    "error": "No hospitals found near this location.",
}

def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def _fetch_url(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_hospitals(lat: float, lng: float, radius_miles: float = 25) -> dict[str, Any]:
    print(f"[hospital_service] Fetching hospitals near lat={lat}, lng={lng}, radius={radius_miles}mi")

    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        print("[hospital_service] GOOGLE_PLACES_API_KEY missing")
        return _DEFAULT_RESPONSE.copy()

    radius_meters = int(radius_miles * 1609.34)
    resources = []
    seen_ids = set()

    for keyword in ["hospital", "clinic", "urgent care"]:
        params = urllib.parse.urlencode({
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "keyword": keyword,
            "type": "hospital",
            "key": api_key,
        })
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?{params}"

        try:
            data = _fetch_url(url)
            status = data.get("status", "")
            results = data.get("results", [])
            print(f"[hospital_service] Google Places '{keyword}': status={status}, count={len(results)}")

            for place in results:
                place_id = place.get("place_id", "")
                if place_id in seen_ids:
                    continue
                seen_ids.add(place_id)

                place_lat = place["geometry"]["location"]["lat"]
                place_lng = place["geometry"]["location"]["lng"]
                distance  = _haversine_miles(lat, lng, place_lat, place_lng)

                if distance > radius_miles:
                    continue

                name  = place.get("name", "Unknown Medical Facility")
                types = place.get("types", [])

                if "hospital" in types:
                    facility_type = "hospital"
                elif "doctor" in types or "clinic" in name.lower():
                    facility_type = "clinic"
                else:
                    facility_type = "urgent_care"

                resources.append({
                    "id": place_id,
                    "name": name,
                    "type": facility_type,
                    "lat": place_lat,
                    "lng": place_lng,
                    "address": place.get("vicinity", ""),
                    "phone": "",
                    "distance_miles": round(distance, 2),
                    "status": "open" if place.get("opening_hours", {}).get("open_now") else "unknown",
                    "emergency_services": facility_type == "hospital",
                    "notes": f"Rating: {place.get('rating', 'N/A')}",
                })

        except Exception as e:
            print(f"[hospital_service] Failed for keyword={keyword}: {e}")
            continue

    if not resources:
        print("[hospital_service] No hospitals found")
        return _DEFAULT_RESPONSE.copy()

    resources.sort(key=lambda x: x["distance_miles"])
    print(f"[hospital_service] Found {len(resources)} hospitals")
    return {"source": "google_places", "resources": resources}