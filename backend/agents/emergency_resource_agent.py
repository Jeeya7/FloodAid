# emergency_resource_agent.py
#
# Fast two-phase pipeline:
#   Phase 1 — resource_collection_step  (Python, parallel HTTP)
#   Phase 2 — resource_analyst_agent    (single LLM call)
#            + distance_ranking_step    (Python, runs in parallel with LLM)
#   Phase 3 — python_scoring_step       (Python, no LLM)
#   Phase 4 — response_formatter_step   (Python, no LLM)
#
# Previously: 3 LLM calls in 2 sequential rounds.
# Now:        1 LLM call, overlapped with distance math.

import json
import math
from datetime import datetime, timezone
from typing import Any
from concurrent.futures import ThreadPoolExecutor

from openrouter_client import chat, parse_json_response
from tools.resource_tools import (
    get_food_resources_tool,
    get_hospitals_tool,
    get_shelters_tool,
    create_bounds_tool,
)

MAX_RESOURCES = 10
TOP_N         = 3

_WEIGHTS              = {"safety": 0.4, "availability": 0.4, "distance": 0.2}
_CATEGORY_MULTIPLIER  = {"hospital": 1.2, "shelter": 1.1, "food": 1.0}

_cache: dict[str, Any] = {}


# ── Fallback ──────────────────────────────────────────────────────────────────

def _fallback_analysis(resources: list[dict]) -> dict[str, Any]:
    return {
        "resources": [
            {
                "id":                 r["id"],
                "safety_score":       0.5,
                "safety_level":       "moderate",
                "availability_score": 0.5 if r.get("status") != "closed" else 0.0,
                "status":             r.get("status", "unknown"),
                "reasoning":          "Analysis unavailable; using default scores.",
            }
            for r in resources
        ],
        "summary": "Resources ranked by estimated suitability.",
    }


# ── Phase 1 — resource_collection_step ───────────────────────────────────────

def resource_collection_step(lat: float, lng: float, radius_miles: float = 25) -> list[dict[str, Any]]:
    create_bounds_tool.invoke({"lat": lat, "lng": lng})

    with ThreadPoolExecutor(max_workers=3) as ex:
        food_f     = ex.submit(get_food_resources_tool.invoke,  {"lat": lat, "lng": lng, "radius_miles": radius_miles})
        hospital_f = ex.submit(get_hospitals_tool.invoke,       {"lat": lat, "lng": lng, "radius_miles": radius_miles})
        shelter_f  = ex.submit(get_shelters_tool.invoke,        {"lat": lat, "lng": lng, "radius_miles": radius_miles})

        food_r, hospital_r, shelter_r = food_f.result(), hospital_f.result(), shelter_f.result()

    flat: list[dict[str, Any]] = []
    for r in food_r.get("resources", []):
        flat.append({**r, "category": "food"})
    for r in hospital_r.get("resources", []):
        flat.append({**r, "category": "hospital"})
    for r in shelter_r.get("resources", []):
        flat.append({**r, "category": "shelter"})

    return flat[:MAX_RESOURCES]


# ── Phase 2a — resource_analyst_agent (single LLM call) ──────────────────────

def resource_analyst_agent(resources: list[dict[str, Any]]) -> dict[str, Any]:
    system = (
        "You are a flood emergency resource analyst. "
        "For each resource score BOTH safety AND availability, then write one-sentence reasoning. "
        "Consider: resource type, flood exposure, open/closed status, capacity. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"resources":['
        '{"id":"string","safety_score":0.0,"safety_level":"low|moderate|high",'
        '"availability_score":0.0,"status":"open|closed|unknown","reasoning":"string"}'
        '],"summary":"one sentence"}'
    )
    user = "Resources:\n" + json.dumps(
        [
            {
                "id":       r["id"],
                "name":     r["name"],
                "category": r["category"],
                "address":  r.get("address", ""),
                "status":   r.get("status", "unknown"),
                "capacity": r.get("capacity"),
                "notes":    r.get("notes", ""),
            }
            for r in resources
        ],
        separators=(",", ":"),
    )
    try:
        raw = chat(system, user, max_tokens=600)
        return parse_json_response(raw)
    except Exception as exc:
        result = _fallback_analysis(resources)
        result["error"] = str(exc)
        return result


# ── Phase 2b — distance_ranking_step ─────────────────────────────────────────

def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 3_958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_ranking_step(resources: list[dict[str, Any]], user_lat: float, user_lng: float) -> list[dict[str, Any]]:
    enriched = []
    for r in resources:
        dist = _haversine_miles(user_lat, user_lng, r.get("lat", user_lat), r.get("lng", user_lng))
        enriched.append({**r, "distance_miles": round(dist, 2)})

    if not enriched:
        return enriched

    max_dist = max(r["distance_miles"] for r in enriched) or 1.0
    for r in enriched:
        r["distance_score"] = round(1.0 - (r["distance_miles"] / max_dist), 4)

    return enriched


# ── Phase 3 — python_scoring_step ────────────────────────────────────────────

def python_scoring_step(
    resources: list[dict[str, Any]],
    analysis_map: dict[str, dict],
) -> dict[str, Any]:
    scored = []
    for r in resources:
        rid    = r["id"]
        info   = analysis_map.get(rid, {})
        status = info.get("status", r.get("status", "unknown"))

        safety_score       = info.get("safety_score",       0.5)
        availability_score = info.get("availability_score", 0.5)
        distance_score     = r.get("distance_score",        0.5)
        category           = r.get("category", "food")

        base  = (
            safety_score       * _WEIGHTS["safety"] +
            availability_score * _WEIGHTS["availability"] +
            distance_score     * _WEIGHTS["distance"]
        )
        score = base * _CATEGORY_MULTIPLIER.get(category, 1.0)
        if status == "closed":
            score *= 0.1

        scored.append({
            **r,
            "overall_score":      round(min(score, 1.0), 4),
            "safety_score":       safety_score,
            "availability_score": availability_score,
            "status":             status,
            "reasoning":          info.get("reasoning", f"Score estimated from safety, availability, and distance."),
        })

    scored.sort(key=lambda x: x["overall_score"], reverse=True)

    top_by_category: dict[str, list[str]] = {"hospital": [], "shelter": [], "food": []}
    top_ids: set[str] = set()
    for r in scored:
        cat = r.get("category")
        if cat in top_by_category and len(top_by_category[cat]) < TOP_N:
            top_by_category[cat].append(r["id"])
            top_ids.add(r["id"])

    ranked_resources = [
        {
            "id":            r["id"],
            "overall_score": r["overall_score"],
            "recommended":   r["id"] in top_ids,
            "reasoning":     r["reasoning"],
        }
        for r in scored
    ]

    return {
        "scored":           scored,
        "ranked_resources": ranked_resources,
        "top_by_category":  top_by_category,
    }


# ── Phase 4 — response_formatter_step ────────────────────────────────────────

def response_formatter_step(
    scored: list[dict[str, Any]],
    ranked_resources: list[dict],
    top_by_category: dict[str, list[str]],
    summary: str,
) -> dict[str, Any]:
    resource_lookup = {r["id"]: r for r in scored}
    rank_lookup     = {r["id"]: r for r in ranked_resources}

    def build_top(category: str) -> list[dict]:
        results = []
        for rid in top_by_category.get(category, []):
            base = resource_lookup.get(rid, {})
            rank = rank_lookup.get(rid, {})
            if base and rank:
                results.append({
                    "id":             rid,
                    "name":           base.get("name", "Unknown"),
                    "type":           base.get("category", "unknown"),
                    "lat":            base.get("lat", 0),
                    "lng":            base.get("lng", 0),
                    "distance_miles": base.get("distance_miles", 0),
                    "overall_score":  rank.get("overall_score", 0),
                    "status":         base.get("status", "unknown"),
                    "reasoning":      rank.get("reasoning", ""),
                })
        return results

    all_ranked = []
    for rank in ranked_resources:
        rid  = rank["id"]
        base = resource_lookup.get(rid, {})
        all_ranked.append({
            "id":             rid,
            "name":           base.get("name", "Unknown"),
            "type":           base.get("category", "unknown"),
            "lat":            base.get("lat", 0),
            "lng":            base.get("lng", 0),
            "distance_miles": base.get("distance_miles", 0),
            "overall_score":  rank.get("overall_score", 0),
            "status":         base.get("status", "unknown"),
            "reasoning":      rank.get("reasoning", ""),
        })

    return {
        "recommended_resources": {
            "hospital": build_top("hospital"),
            "shelter":  build_top("shelter"),
            "food":     build_top("food"),
        },
        "ranked_resources": all_ranked,
        "summary":          summary,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def emergency_resource_agent(lat: float, lng: float) -> dict[str, Any]:
    key = f"{round(lat, 2)},{round(lng, 2)}"
    if key in _cache:
        return _cache[key]

    resources = resource_collection_step(lat, lng)

    if not resources:
        return {
            "recommended_resources": {"hospital": [], "shelter": [], "food": []},
            "ranked_resources":      [],
            "summary":               "No emergency resources found near this location.",
            "generated_at":          datetime.now(timezone.utc).isoformat(),
        }

    # Phase 2: LLM analysis and distance math run in parallel
    with ThreadPoolExecutor(max_workers=2) as ex:
        analysis_future = ex.submit(resource_analyst_agent, resources)
        distance_future = ex.submit(distance_ranking_step, resources, lat, lng)

        analysis_result = analysis_future.result()
        resources       = distance_future.result()

    analysis_map: dict[str, dict] = {
        r["id"]: r for r in analysis_result.get("resources", [])
    }
    summary = analysis_result.get("summary", "Resources ranked by flood emergency suitability.")

    # Phase 3: pure Python scoring
    scoring = python_scoring_step(resources, analysis_map)

    # Phase 4: format response
    result = response_formatter_step(
        scored           = scoring["scored"],
        ranked_resources = scoring["ranked_resources"],
        top_by_category  = scoring["top_by_category"],
        summary          = summary,
    )

    _cache[key] = result
    return result
