"""
Route scoring service — pure scoring logic with no LLM calls.
Agents call choose_route() and get back the safest option.
"""

from typing import Any


# Penalty points subtracted for dangerous route features
_PENALTY_LOW_LYING = 25
_PENALTY_BRIDGE_NEAR_RIVER = 20

# Flood risk rating → score penalty
_FLOOD_RATING_PENALTY: dict[str, int] = {
    "low": 0,
    "moderate": 15,
    "high": 35,
}

# Minutes of travel converted to a small time bonus (lower time → small bonus)
_MAX_TIME_BONUS = 10
_TIME_BONUS_BASELINE_MINUTES = 30


def _score_route(route: dict[str, Any], risk_level: str) -> float:
    """
    Score a single route out of ~100.

    Breakdown:
      - Base safety    : safety_score (0–100)
      - Low-lying road : -25 pts when risk is moderate or high
      - Bridge penalty : -20 pts when risk is high
      - Flood rating   : -0/-15/-35 pts depending on flood_risk_rating
      - Time bonus     : up to +10 pts for shorter travel time
    """
    score = float(route.get("safety_score", 50))

    if risk_level in ("moderate", "high") and route.get("has_low_lying_roads"):
        score -= _PENALTY_LOW_LYING

    if risk_level == "high" and route.get("crosses_bridge_near_river"):
        score -= _PENALTY_BRIDGE_NEAR_RIVER

    flood_rating = route.get("flood_risk_rating", "moderate")
    score -= _FLOOD_RATING_PENALTY.get(flood_rating, 15)

    # Slight bonus for shorter estimated time (max 10 pts)
    minutes = route.get("estimated_time_minutes", _TIME_BONUS_BASELINE_MINUTES)
    time_bonus = max(0.0, _MAX_TIME_BONUS * (1 - minutes / _TIME_BONUS_BASELINE_MINUTES))
    score += time_bonus

    return round(score, 2)


def choose_route(
    routes: list[dict[str, Any]],
    risk: dict[str, Any],
    top_resource: dict[str, Any],
) -> dict[str, Any]:
    """
    Score all routes and return a structured route recommendation.

    Returns a dict with keys:
      route_type, selected_route_name, estimated_time, avoid,
      route_reasoning, is_evacuation_recommended
    """
    risk_level = risk.get("risk_level", "unknown")
    recommended_action = risk.get("recommended_action", "stay_informed")
    is_evacuation_recommended = risk_level == "high" or recommended_action == "evacuate"

    scored_routes = [
        {**r, "_score": _score_route(r, risk_level)}
        for r in routes
    ]
    scored_routes.sort(key=lambda r: r["_score"], reverse=True)
    best = scored_routes[0]

    avoid: list[str] = []
    if risk_level in ("moderate", "high"):
        avoid.append("low-lying river roads")
        avoid.append("roads near rising creeks")
    if risk_level == "high":
        avoid.append("bridges near rivers")
        avoid.append("underpasses")

    resource_name = top_resource.get("name", "the nearest safe resource")

    if is_evacuation_recommended:
        route_type = "safer_evacuation_route"
        reasoning = (
            f"Evacuation is recommended (risk={risk_level}, action={recommended_action}). "
            f"'{best['name']}' scores highest at {best['_score']} pts — it avoids flood-prone "
            f"roads and leads toward {resource_name}."
        )
    elif risk_level == "low":
        route_type = "optional_information_route"
        reasoning = (
            "Risk is low. Movement is optional. "
            f"'{best['name']}' is available should conditions change."
        )
    else:
        route_type = "preparedness_route"
        reasoning = (
            f"Risk is {risk_level}. '{best['name']}' scores {best['_score']} pts and "
            f"provides a ready path to {resource_name} if conditions worsen."
        )

    return {
        "route_type": route_type,
        "selected_route_name": best["name"],
        "estimated_time": f"{best['estimated_time_minutes']} minutes",
        "avoid": avoid,
        "route_reasoning": reasoning,
        "is_evacuation_recommended": is_evacuation_recommended,
    }
