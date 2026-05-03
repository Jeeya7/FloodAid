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
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from concurrent.futures import ThreadPoolExecutor


from openrouter_client import chat, parse_json_response
from tools.resource_tools import (
    get_food_resources_tool,
    get_hospitals_tool,
    get_shelters_tool,
    create_bounds_tool
)

# Cap resources sent to the LLM to keep prompts small and stay inside quota
MAX_RESOURCES = 10

BASE_DIR = Path(__file__).resolve().parent
AGENT_RESPONSE_PATH = BASE_DIR.parent / "agent_response" / "emergency_resource_agent.json"


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
    ranked = []

    for r in resources:
        status = r.get("status", "unknown")
        score = 0.0 if status == "closed" else r.get("_combined_score", 0.5)

        ranked.append({
            "id": r["id"],
            "overall_score": score,
            "recommended": False,
            "reasoning": "Synthesis unavailable; ranked by fallback score.",
        })

    ranked.sort(key=lambda x: x["overall_score"], reverse=True)

    best_by_category = {
        "hospital": None,
        "shelter": None,
        "food": None,
    }

    lookup = {r["id"]: r for r in resources}

    for item in ranked:
        base = lookup.get(item["id"], {})
        category = base.get("category")

        if category in best_by_category and best_by_category[category] is None:
            best_by_category[category] = item["id"]
            item["recommended"] = True

    return {
        "ranked_resources": ranked,
        "best_by_category": best_by_category,
        "summary": "Synthesis agent failed; resources ranked by fallback estimate.",
    }


# ── Step 1 — resource_collection_step (Python, no LLM) ───────────────────────

def resource_collection_step(
    lat: float,
    lng: float,
    radius_miles: float = 25,
) -> list[dict[str, Any]]:
    """
    Call the three resource tools and flatten all results into a single list.
    Each resource gets a 'category' field ('food', 'hospital', or 'shelter')
    so downstream steps can see what kind of resource it is.
    """
    bounds = create_bounds_tool.invoke({"lat": lat, "lng": lng})
    
    # TODO: Change this
    with ThreadPoolExecutor(max_workers=3) as executor:
        food_future = executor.submit(
            get_food_resources_tool.invoke,
            {"lat": lat, "lng": lng, "radius_miles": radius_miles},
        )

        hospital_future = executor.submit(
            get_hospitals_tool.invoke,
            {"lat": lat, "lng": lng, "radius_miles": radius_miles},
        )

        shelter_future = executor.submit(
            get_shelters_tool.invoke,
            {"lat": lat, "lng": lng, "radius_miles": radius_miles},
        )

        food_result = food_future.result()
        hospital_result = hospital_future.result()
        shelter_result = shelter_future.result()

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
    LLM dynamically combines safety, availability, and distance scores.
    Python only prepares compact inputs and provides fallback if LLM fails.
    """

    scored = []

    for r in resources:
        sid = r["id"]

        scored.append({
            "id": sid,
            "category": r["category"],
            "distance_score": r.get("distance_score", 0.5),
            "safety_score": safety_map.get(sid, {}).get("safety_score", 0.5),
            "availability_score": availability_map.get(sid, {}).get("availability_score", 0.5),
            "status": availability_map.get(sid, {}).get("status", r.get("status", "unknown")),
        })

    system = (
        "You are a flood emergency resource synthesis agent. "
        "Calculate overall_score dynamically for each resource using safety_score, availability_score, "
        "distance_score, status, category, and emergency usefulness. "
        "Heavily penalize closed resources. "
        "Rank all resources overall. "
        "Also choose the best resource id for each category: hospital, shelter, and food. "
        "If a category has no resources, use null. "
        "Return ONLY valid JSON. No markdown. No explanation outside JSON. "
        "Do not show calculations. "
        "Use this exact schema:\n"
        '{"ranked_resources":[{"id":"string","overall_score":0.0,"recommended":false,"reasoning":"string"}],'
        '"best_by_category":{"hospital":null,"shelter":null,"food":null},'
        '"summary":"string"}'
    )

    user = "Resources:\n" + json.dumps(scored, separators=(",", ":"))

    try:
        raw = chat(system, user)

        print("\n=== SYNTHESIS RAW ===\n", raw)

        parsed = parse_json_response(raw)

        if not isinstance(parsed, dict):
            raise ValueError("Synthesis response was not a JSON object")

        if "ranked_resources" not in parsed:
            raise ValueError("Synthesis JSON missing ranked_resources")

        if "best_by_category" not in parsed:
            raise ValueError("Synthesis JSON missing best_by_category")

        return parsed

    except Exception as exc:
        print("\n=== SYNTHESIS ERROR ===\n", str(exc))
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

    if synthesis is None:
        synthesis = _fallback_synthesis(resources)

    resource_lookup = {r["id"]: r for r in resources}
    ranked_raw: list[dict] = synthesis.get("ranked_resources", [])
    best_by_category = synthesis.get("best_by_category", {})

    ranked_resources = []

    for item in ranked_raw:
        rid = item.get("id")
        base = resource_lookup.get(rid, {})

        ranked_resources.append({
            "id": rid,
            "name": base.get("name", "Unknown"),
            "type": base.get("category", "unknown"),
            "lat": base.get("lat", 0),
            "lng": base.get("lng", 0),
            "distance_miles": base.get("distance_miles", 0),
            "overall_score": item.get("overall_score", 0),
            "status": availability_map.get(rid, {}).get(
                "status",
                base.get("status", "unknown"),
            ),
            "reasoning": item.get("reasoning", ""),
        })

    ranked_resources.sort(key=lambda x: x["overall_score"], reverse=True)

    def build_recommended(category: str):
        rid = best_by_category.get(category)

        if rid is None:
            return None

        base = resource_lookup.get(rid)
        ranked_item = next((r for r in ranked_resources if r["id"] == rid), None)

        if not base or not ranked_item:
            return None

        return ranked_item

    return {
        "recommended_resources": {
            "hospital": build_recommended("hospital"),
            "shelter": build_recommended("shelter"),
            "food": build_recommended("food"),
        },
        "ranked_resources": ranked_resources,
        "summary": synthesis.get("summary", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_agent_response(payload: dict[str, Any]) -> None:
    try:
        AGENT_RESPONSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AGENT_RESPONSE_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ── Main entry point ──────────────────────────────────────────────────────────

def emergency_resource_agent(lat, lng) -> dict[str, Any]:
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

    # ── Step 1: collect raw data (Python, no LLM) ────────────────────────────
    resources = resource_collection_step(lat, lng)

    if not resources:
        result = {
            "recommended_resource": None,
            "ranked_resources": [],
            "summary": "No emergency resources found near this location.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_agent_response(result)
        return result

    # ── Step 2: safety scoring (LLM) ────────────────────────────────────────
    safety_result = resource_safety_agent(resources)
    safety_map: dict[str, dict] = {
        r["id"]: r for r in safety_result.get("resources", [])
    }

    # ── Step 3: availability scoring (LLM) ───────────────────────────────────
    availability_result = availability_agent(resources)
    availability_map: dict[str, dict] = {
        r["id"]: r for r in availability_result.get("resources", [])
    }

    # ── Step 4: distance ranking (Python) ────────────────────────────────────
    resources = distance_ranking_step(resources, lat, lng)
    
    # ── Step 5: synthesis (LLM) ──────────────────────────────────────────────
    synthesis = resource_synthesis_agent(resources, safety_map, availability_map)

    # ── Step 6: format final output (Python) ─────────────────────────────────
    final = response_formatter_step(resources, safety_map, availability_map, synthesis)

    _save_agent_response(final)
    return final
