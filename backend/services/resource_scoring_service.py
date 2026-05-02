"""
Resource scoring service — pure scoring logic with no LLM calls.
Agents call rank_resources() and get back an ordered list.
"""

from typing import Any


# How useful each resource type is by default
_BASE_TYPE_SCORE: dict[str, float] = {
    "shelter": 35.0,
    "hospital": 25.0,
    "food_support": 20.0,
}

# Extra weight given to a type when risk is elevated
_HIGH_RISK_BONUS: dict[str, float] = {
    "shelter": 15.0,
    "hospital": 10.0,
    "food_support": 5.0,
}

_MODERATE_RISK_BONUS: dict[str, float] = {
    "shelter": 8.0,
    "hospital": 5.0,
    "food_support": 3.0,
}


def _score_resource(resource: dict[str, Any], risk_level: str) -> float:
    """
    Score a single resource out of ~100.

    Breakdown:
      - Distance   : up to 30 pts  (closer is better, 0 pts at 6+ miles)
      - Type       : 20–35 pts     (varies by resource type)
      - Safety     : up to 40 pts  (safety_score * 0.4)
      - Risk bonus : 0–15 pts      (extra weight for the most useful type at high risk)
    """
    distance_score = max(0.0, 30.0 - resource["distance_miles"] * 5.0)

    base_type_score = _BASE_TYPE_SCORE.get(resource["resource_type"], 10.0)

    if risk_level == "high":
        type_bonus = _HIGH_RISK_BONUS.get(resource["resource_type"], 0.0)
    elif risk_level == "moderate":
        type_bonus = _MODERATE_RISK_BONUS.get(resource["resource_type"], 0.0)
    else:
        type_bonus = 0.0

    safety_score = resource.get("safety_score", 0) * 0.4

    # Closed resources are unusable
    if not resource.get("is_open", True):
        return 0.0

    return round(distance_score + base_type_score + type_bonus + safety_score, 2)


def rank_resources(
    resources: list[dict[str, Any]],
    risk: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Score and sort resources from best to worst for the given risk context.

    Returns a new list — original dicts are not mutated.
    Each dict gets a new 'score' key added.
    """
    risk_level = risk.get("risk_level", "unknown")

    scored = [
        {**resource, "score": _score_resource(resource, risk_level)}
        for resource in resources
    ]

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored
