"""
Mock data service — returns static demo data for location, environment,
resources, and routes. Replace these with real API calls in production.
"""

from typing import Any


def get_mock_location() -> dict[str, Any]:
    return {
        "lat": 44.5646,
        "lng": -123.2620,
        "city": "Corvallis",
        "state": "OR",
    }


def get_mock_environmental_data() -> dict[str, Any]:
    return {
        "rain_forecast_inches": 2.4,
        "water_level_status": "high",
        "streamflow_status": "above_normal",
        "weather_alert": "flood_watch",
        "nearest_gauge_distance_miles": 8.2,
        "water_level_trend": "rising",
    }


def get_mock_resources() -> list[dict[str, Any]]:
    return [
        {
            "name": "Corvallis Community Shelter",
            "resource_type": "shelter",
            "distance_miles": 1.8,
            "safety_score": 91,
            "address": "Downtown Corvallis",
            "is_open": True,
        },
        {
            "name": "Good Samaritan Regional Medical Center",
            "resource_type": "hospital",
            "distance_miles": 3.4,
            "safety_score": 96,
            "address": "North Corvallis",
            "is_open": True,
        },
        {
            "name": "Benton County Food and Support Center",
            "resource_type": "food_support",
            "distance_miles": 2.2,
            "safety_score": 87,
            "address": "Central Corvallis",
            "is_open": True,
        },
    ]


def get_mock_routes() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "highland_arterial",
            "name": "Highland Arterial Route",
            "description": "Higher-elevation arterial roads away from river corridor",
            "estimated_time_minutes": 18,
            "safety_score": 92,
            "has_low_lying_roads": False,
            "crosses_bridge_near_river": False,
            "flood_risk_rating": "low",
        },
        {
            "route_id": "riverside_shortcut",
            "name": "Riverside Shortcut",
            "description": "Faster but passes through river flood zone",
            "estimated_time_minutes": 9,
            "safety_score": 51,
            "has_low_lying_roads": True,
            "crosses_bridge_near_river": True,
            "flood_risk_rating": "high",
        },
        {
            "route_id": "midtown_connector",
            "name": "Midtown Connector",
            "description": "Mixed elevation route through midtown",
            "estimated_time_minutes": 12,
            "safety_score": 74,
            "has_low_lying_roads": False,
            "crosses_bridge_near_river": True,
            "flood_risk_rating": "moderate",
        },
    ]
