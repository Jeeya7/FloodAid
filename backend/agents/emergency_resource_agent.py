# emergency_resource_agent.py
#
# Multi-step pipeline that finds, evaluates, and ranks emergency resources
# (shelters, hospitals, food) near a given location.
#
# Flow:
#   1. resource_collection_step  — Python calls tools; no LLM
#   2. resource_safety_agent     — LLM scores how safe each resource is
#   3. availability_agent        — LLM scores whether each resource is usable
#   4. distance_ranking_step     — Python computes and normalises distance scores
#   5. resource_synthesis_agent  — LLM combines all scores → ranked list + best pick
#   6. response_formatter_step   — Python merges everything into frontend-ready JSON
#
# The LLM never calls external APIs — it only reasons over data Python fetched.

import json
import math
from datetime import datetime, timezone
from typing import Any

from openrouter_client import chat, parse_json_response
from tools.resource_tools import (
    get_food_resources_tool,
    get_hospitals_tool,
    get_shelters_tool,
)

# Cap resources sent to the LLM to keep prompts small and stay inside quota
MAX_RESOURCES = 10


# ── Fallback templates ────────────────────────────────────────────────────────

def _fallback_safety(resources: list[dict]) -> dict[str, Any]:
    return {
        "resources": [
            {
                "id": r["id"],
                "safety_score": 0.5,
                "safety_level": "moderate",
                "reasoning": "Safety check unavailable; defaulting to moderate.",
            }
            for r in resources
        ]
    }


def _fallback_availability(resources: list[dict]) -> dict[str, Any]:
    return {
        "resources": [
            {
                "id": r["id"],
                "availability_score": 0.5 if r.get("status") != "closed" else 0.0,
                "status": r.get("status", "unknown"),
                "reasoning": "Availability check unavailable; estimated from status field.",
            }
            for r in resources
        ]
    }


def _fallback_synthesis(resources: list[dict]) -> dict[str, Any]:
    # Sort by whatever combined score fields exist; pick the first open resource
    open_resources = [r for r in resources if r.get("status") != "closed"]
    best = open_resources[0] if open_resources else (resources[0] if resources else {})
    return {
        "ranked_resources": [
            {
                "id": r["id"],
                "overall_score": r.get("_combined_score", 0.5),
                "recommended": r["id"] == best.get("id"),
                "reasoning": "Synthesis unavailable; ranked by combined score.",
            }
            for r in resources
        ],
        "best_option_id": best.get("id", ""),
        "summary": "Synthesis agent failed; resources ranked by combined score estimate.",
    }


# ── Step 1 — resource_collection_step (Python, no LLM) ───────────────────────

def resource_collection_step(
    lat: float,
    lng: float,
    radius_miles: float,
) -> list[dict[str, Any]]:
    """
    Call the three resource tools and flatten all results into a single list.
    Each resource gets a 'category' field ('food', 'hospital', or 'shelter')
    so downstream steps can see what kind of resource it is.
    """
    food_result     = get_food_resources_tool.invoke({"lat": lat, "lng": lng, "radius_miles": radius_miles})
    hospital_result = get_hospitals_tool.invoke({"lat": lat, "lng": lng, "radius_miles": radius_miles})
    shelter_result  = get_shelters_tool.invoke({"lat": lat, "lng": lng, "radius_miles": radius_miles})

    flat: list[dict[str, Any]] = []

    for resource in food_result.get("resources", []):
        flat.append({**resource, "category": "food"})

    for resource in hospital_result.get("resources", []):
        flat.append({**resource, "category": "hospital"})

    for resource in shelter_result.get("resources", []):
        flat.append({**resource, "category": "shelter"})

    # Limit to MAX_RESOURCES to keep LLM prompts short
    return flat[:MAX_RESOURCES]


# ── Step 2 — resource_safety_agent (LLM) ─────────────────────────────────────

def resource_safety_agent(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Ask the LLM to score how safe each resource is during a flood emergency.
    Considers resource type, location context, and emergency suitability.
    """
    system = (
        "You are a flood emergency safety analyst. "
        "Score how safe and suitable each resource is during an active flood. "
        "Consider: resource type, whether it serves vulnerable populations, "
        "and whether its location is likely to be flood-affected. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"resources":[{"id":"string","safety_score":0.0,"safety_level":"low|moderate|high","reasoning":"string"}]}'
    )
    user = "Resources:\n" + json.dumps(
        [{"id": r["id"], "name": r["name"], "category": r["category"],
          "address": r.get("address", ""), "notes": r.get("notes", "")}
         for r in resources],
        separators=(",", ":"),
    )

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        result = _fallback_safety(resources)
        result["error"] = str(exc)
        return result


# ── Step 3 — availability_agent (LLM) ────────────────────────────────────────

def availability_agent(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Ask the LLM to evaluate whether each resource is currently usable.
    Considers status, capacity, and emergency suitability.
    """
    system = (
        "You are an emergency resource availability analyst. "
        "Evaluate whether each resource is usable right now during a flood emergency. "
        "Consider: open/closed status, capacity, and emergency readiness. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"resources":[{"id":"string","availability_score":0.0,"status":"open|closed|unknown","reasoning":"string"}]}'
    )
    user = "Resources:\n" + json.dumps(
        [{"id": r["id"], "name": r["name"], "status": r.get("status", "unknown"),
          "capacity": r.get("capacity"), "notes": r.get("notes", "")}
         for r in resources],
        separators=(",", ":"),
    )

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        result = _fallback_availability(resources)
        result["error"] = str(exc)
        return result


# ── Step 4 — distance_ranking_step (Python) ───────────────────────────────────

def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in miles between two lat/lng points."""
    r = 3_958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_ranking_step(
    resources: list[dict[str, Any]],
    user_lat: float,
    user_lng: float,
) -> list[dict[str, Any]]:
    """
    Compute the distance from the user to each resource and add a normalised
    distance_score (1.0 = closest, 0.0 = farthest).
    """
    enriched = []
    for r in resources:
        resource_lat = r.get("lat", user_lat)
        resource_lng = r.get("lng", user_lng)
        dist = _haversine_miles(user_lat, user_lng, resource_lat, resource_lng)
        enriched.append({**r, "distance_miles": round(dist, 2)})

    if not enriched:
        return enriched

    max_dist = max(r["distance_miles"] for r in enriched) or 1.0
    for r in enriched:
        # Resources at distance 0 get score 1.0; farthest gets 0.0
        r["distance_score"] = round(1.0 - (r["distance_miles"] / max_dist), 4)

    return enriched


# ── Step 5 — resource_synthesis_agent (LLM) ───────────────────────────────────

def resource_synthesis_agent(
    resources: list[dict[str, Any]],
    safety_map: dict[str, dict],
    availability_map: dict[str, dict],
) -> dict[str, Any]:
    """
    Combine safety, availability, and distance scores into a final ranking.
    The LLM determines overall scores and picks the best option.
    """
    # Pre-attach scores to each resource so the prompt is self-contained
    scored = []
    for r in resources:
        sid = r["id"]
        scored.append({
            "id":                 sid,
            "name":               r["name"],
            "category":           r["category"],
            "distance_miles":     r.get("distance_miles", 0),
            "distance_score":     r.get("distance_score", 0.5),
            "safety_score":       safety_map.get(sid, {}).get("safety_score", 0.5),
            "safety_level":       safety_map.get(sid, {}).get("safety_level", "moderate"),
            "availability_score": availability_map.get(sid, {}).get("availability_score", 0.5),
            "status":             availability_map.get(sid, {}).get("status", r.get("status", "unknown")),
        })
        # Store combined estimate for fallback use
        r["_combined_score"] = round(
            scored[-1]["safety_score"] * 0.35
            + scored[-1]["availability_score"] * 0.35
            + scored[-1]["distance_score"] * 0.30,
            4,
        )

    system = (
        "You are a flood emergency resource coordinator. "
        "Each resource has safety, availability, and distance scores (all 0–1, higher is better). "
        "Combine them into an overall_score. Pick the single best option for someone needing help now. "
        "Heavily penalise closed resources. Prefer the closest open, safe resource. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"ranked_resources":[{"id":"string","overall_score":0.0,"recommended":false,"reasoning":"string"}],'
        '"best_option_id":"string","summary":"string"}'
    )
    user = "Resources:\n" + json.dumps(scored, separators=(",", ":"))

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        result = _fallback_synthesis(resources)
        result["error"] = str(exc)
        return result


# ── Step 6 — response_formatter_step (Python) ────────────────────────────────

def response_formatter_step(
    resources: list[dict[str, Any]],
    safety_map: dict[str, dict],
    availability_map: dict[str, dict],
    synthesis: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge all step outputs into the final frontend-ready JSON.
    Pure Python — no LLM call.
    """
    resource_lookup = {r["id"]: r for r in resources}
    ranked_raw: list[dict] = synthesis.get("ranked_resources", [])
    best_id: str = synthesis.get("best_option_id", "")

    ranked_resources = []
    for item in ranked_raw:
        rid = item["id"]
        base = resource_lookup.get(rid, {})
        ranked_resources.append({
            "id":            rid,
            "name":          base.get("name", "Unknown"),
            "type":          base.get("category", "unknown"),
            "distance_miles": base.get("distance_miles", 0),
            "overall_score": item.get("overall_score", 0),
            "status":        availability_map.get(rid, {}).get("status", base.get("status", "unknown")),
        })

    # Sort by overall_score descending so the frontend can use the list directly
    ranked_resources.sort(key=lambda x: x["overall_score"], reverse=True)

    # Build the recommended resource block
    best_base = resource_lookup.get(best_id, {})
    best_synthesis = next((r for r in ranked_raw if r["id"] == best_id), {})
    recommended_resource = {
        "id":             best_id,
        "name":           best_base.get("name", "Unknown"),
        "type":           best_base.get("category", "unknown"),
        "lat":            best_base.get("lat", 0),
        "lng":            best_base.get("lng", 0),
        "distance_miles": best_base.get("distance_miles", 0),
        "status":         availability_map.get(best_id, {}).get("status", best_base.get("status", "unknown")),
        "reasoning":      best_synthesis.get("reasoning", synthesis.get("summary", "")),
    }

    return {
        "recommended_resource": recommended_resource,
        "ranked_resources":     ranked_resources,
        "summary":              synthesis.get("summary", ""),
        "generated_at":         datetime.now(timezone.utc).isoformat(),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def emergency_resource_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Full multi-step emergency resource pipeline.

    State keys read:
      lat          : float  — user latitude (required)
      lng          : float  — user longitude (required)
      radius_miles : float  — search radius (default 10)
      debug_steps  : list   — appended to throughout the pipeline

    State keys written:
      recommended_resource, ranked_resources, summary,
      generated_at, debug_steps
    """
    lat          = state.get("lat", 44.6367)
    lng          = state.get("lng", -124.0535)
    radius_miles = state.get("radius_miles", 10)
    debug_steps: list[str] = list(state.get("debug_steps", []))

    # ── Step 1: collect raw data (Python, no LLM) ────────────────────────────
    resources = resource_collection_step(lat, lng, radius_miles)
    debug_steps.append(
        f"resource_collection_step: fetched {len(resources)} resources "
        f"(food + hospitals + shelters) within {radius_miles} miles."
    )

    if not resources:
        debug_steps.append("No resources found — returning empty result.")
        return {
            **state,
            "recommended_resource": None,
            "ranked_resources": [],
            "summary": "No emergency resources found near this location.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "debug_steps": debug_steps,
        }

    # ── Step 2: safety scoring (LLM) ────────────────────────────────────────
    safety_result = resource_safety_agent(resources)
    safety_map: dict[str, dict] = {
        r["id"]: r for r in safety_result.get("resources", [])
    }
    debug_steps.append(
        f"resource_safety_agent: scored {len(safety_map)} resources. "
        f"Error: {safety_result.get('error', 'none')}"
    )

    # ── Step 3: availability scoring (LLM) ───────────────────────────────────
    availability_result = availability_agent(resources)
    availability_map: dict[str, dict] = {
        r["id"]: r for r in availability_result.get("resources", [])
    }
    debug_steps.append(
        f"availability_agent: evaluated {len(availability_map)} resources. "
        f"Error: {availability_result.get('error', 'none')}"
    )

    # ── Step 4: distance ranking (Python) ────────────────────────────────────
    resources = distance_ranking_step(resources, lat, lng)
    debug_steps.append(
        "distance_ranking_step: computed haversine distances and normalised scores."
    )

    # ── Step 5: synthesis (LLM) ──────────────────────────────────────────────
    synthesis = resource_synthesis_agent(resources, safety_map, availability_map)
    debug_steps.append(
        f"resource_synthesis_agent: best_option_id={synthesis.get('best_option_id', 'none')}. "
        f"Error: {synthesis.get('error', 'none')}"
    )

    # ── Step 6: format final output (Python) ─────────────────────────────────
    final = response_formatter_step(resources, safety_map, availability_map, synthesis)
    debug_steps.append(
        f"response_formatter_step: built final JSON with "
        f"{len(final['ranked_resources'])} ranked resources."
    )

    return {
        **state,
        **final,
        "debug_steps": debug_steps,
    }
