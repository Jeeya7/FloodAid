import requests
from typing import Any, List
import numpy as np
from sklearn.neighbors import BallTree



USGS_SITE_URL = "https://waterservices.usgs.gov/nwis/iv"


def get_all_usgs_stations() -> list[dict[str, Any]]:
    """
    USGS station ingestion with deduplication.
    Returns all active USGS gauges with coordinates.
    """

    stations = []
    seen = set()

    start_index = 0
    params = {
        "format": "json",
        "siteStatus": "all",          # stream sites (important for flood modeling)
        "stateCd" : "or",
    }

    r = requests.get(USGS_SITE_URL, params=params, timeout=60)
    print("here")

    data = r.json()

    time_series = data.get("value", {}).get("timeSeries", [])

    for item in time_series:
        try:
            src = item["sourceInfo"]

            site_id = src["siteCode"][0]["value"]

            if site_id in seen:
                continue
            seen.add(site_id)

            geo = src.get("geoLocation", {}) \
                        .get("geogLocation", {})

            lat = geo.get("latitude")
            lng = geo.get("longitude")

            if lat is None or lng is None:
                continue

            stations.append({
                "site_id": site_id,
                "name": src.get("siteName"),
                "lat": float(lat),
                "lng": float(lng),
                "state": src.get("siteProperty", [])
            })

        except Exception:
            continue


    return stations


class USGSStationIndex:
    def __init__(self, stations: list[dict]):
        self.stations = stations

        coords = np.array([
            [s["lat"], s["lng"]] for s in stations
        ])

        # convert degrees → radians for haversine
        self.tree = BallTree(np.radians(coords), metric="haversine")

    def nearest(self, lat: float, lng: float, k: int = 3):
        dist, idx = self.tree.query(
            np.radians([[lat, lng]]),
            k=k
        )

        results = []
        for i in idx[0]:
            results.append(self.stations[i])

        return results
    

import requests
from typing import Any


def get_usgs_streamflow(site_id: str) -> dict[str, Any]:
    url = "https://waterservices.usgs.gov/nwis/iv/"
    
    params = {
        "format": "json",
        "sites": site_id,
        "parameterCd": "00060",  # discharge (flow rate)
        "siteStatus": "all"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    values = data["value"]["timeSeries"][0]["values"][0]["value"]

    latest = float(values[-1]["value"])
    previous = float(values[-2]["value"]) if len(values) > 1 else latest

    trend = (
        "rising" if latest > previous
        else "falling" if latest < previous
        else "stable"
    )

    return {
        "streamflow_cfs": latest,
        "trend": trend,
    }


def aggregate_risk(features: list[dict]) -> dict:
    """
    Simple baseline fusion model
    """

    avg_flow = sum(f["streamflow"] for f in features) / len(features)
    rising = sum(1 for f in features if f["trend"] == "rising")

    flood_risk_score = (
        0.5 * min(avg_flow / 2000, 1.0) +
        0.5 * (rising / len(features))
    )

    return {
        "flood_risk_score": round(flood_risk_score, 3),
        "risk_level": (
            "high" if flood_risk_score > 0.7
            else "moderate" if flood_risk_score > 0.4
            else "low"
        )
    }