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
#   5. resource_synthesis_agent  — Python scores + LLM adds reasoning/summary
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


# How many top resources to return per category
TOP_N = 3

# Weights used by Python scoring in resource_synthesis_agent
_WEIGHTS = {"safety": 0.4, "availability": 0.4, "distance": 0.2}
_CATEGORY_MULTIPLIER = {"hospital": 1.2, "shelter": 1.1, "food": 1.0}



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

    top_by_category: dict[str, list[str]] = {"hospital": [], "shelter": [], "food": []}
    lookup = {r["id"]: r for r in resources}

    for item in ranked:
        category = lookup.get(item["id"], {}).get("category")
        if category in top_by_category and len(top_by_category[category]) < TOP_N:
            top_by_category[category].append(item["id"])
            item["recommended"] = True

    return {
        "ranked_resources": ranked,
        "top_by_category": top_by_category,
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

        food_result     = food_future.result()
        hospital_result = hospital_future.result()
        shelter_result  = shelter_future.result()

    flat: list[dict[str, Any]] = []

    for resource in food_result.get("resources", []):
        flat.append({**resource, "category": "food"})

    for resource in hospital_result.get("resources", []):
        flat.append({**resource, "category": "hospital"})

    for resource in shelter_result.get("resources", []):
        flat.append({**resource, "category": "shelter"})

    return flat[:MAX_RESOURCES]


# ── Step 2 — resource_safety_agent (LLM) ─────────────────────────────────────

def resource_safety_agent(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Ask the LLM to score how safe each resource is during a flood emergency.
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
    r = 3_958.8
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


# ── Step 5 — resource_synthesis_agent (Python scoring + LLM reasoning) ────────

def _compute_overall_score(
    r: dict[str, Any],
    safety_map: dict[str, dict],
    availability_map: dict[str, dict],
) -> float:
    """
    Score entirely in Python — no LLM arithmetic, no token burn.
    Formula: weighted(safety, availability, distance) × category_multiplier,
    with a heavy penalty for closed resources.
    """
    rid = r["id"]
    safety_score       = safety_map.get(rid, {}).get("safety_score", 0.5)
    availability_score = availability_map.get(rid, {}).get("availability_score", 0.5)
    distance_score     = r.get("distance_score", 0.5)
    status             = availability_map.get(rid, {}).get("status", r.get("status", "unknown"))
    category           = r.get("category", "food")

    base = (
        safety_score       * _WEIGHTS["safety"] +
        availability_score * _WEIGHTS["availability"] +
        distance_score     * _WEIGHTS["distance"]
    )
    score = base * _CATEGORY_MULTIPLIER.get(category, 1.0)

    if status == "closed":
        score *= 0.1  # heavy penalty

    return round(min(score, 1.0), 4)


def resource_synthesis_agent(
    resources: list[dict[str, Any]],
    safety_map: dict[str, dict],
    availability_map: dict[str, dict],
) -> dict[str, Any]:
    """
    Python computes all scores; LLM only writes one short reasoning sentence
    per resource and a summary. top_by_category holds the top TOP_N ids per category.
    """
    # ── Python scoring ────────────────────────────────────────────────────────
    scored = []
    for r in resources:
        scored.append({
            **r,
            "overall_score":      _compute_overall_score(r, safety_map, availability_map),
            "safety_score":       safety_map.get(r["id"], {}).get("safety_score", 0.5),
            "availability_score": availability_map.get(r["id"], {}).get("availability_score", 0.5),
            "status":             availability_map.get(r["id"], {}).get("status", r.get("status", "unknown")),
        })

    scored.sort(key=lambda x: x["overall_score"], reverse=True)

    # ── top TOP_N per category (Python) ──────────────────────────────────────
    top_by_category: dict[str, list[str]] = {"hospital": [], "shelter": [], "food": []}
    for r in scored:
        cat = r.get("category")
        if cat in top_by_category and len(top_by_category[cat]) < TOP_N:
            top_by_category[cat].append(r["id"])

    # ── LLM: one short reasoning sentence per resource + summary ──────────────
    slim = [
        {
            "id":             r["id"],
            "name":           r["name"],
            "category":       r["category"],
            "overall_score":  r["overall_score"],
            "status":         r["status"],
            "distance_miles": r.get("distance_miles", 0),
        }
        for r in scored
    ]

    system = (
        "You are a flood emergency resource analyst. "
        "The scores have already been calculated. "
        "Write a short one-sentence reasoning for each resource explaining why it scored as it did, "
        "and a one-sentence overall summary. "
        "Return ONLY valid JSON — no markdown, no calculations:\n"
        '{"reasonings":{"<id>":"<one sentence>"},"summary":"<one sentence>"}'
    )
    user = json.dumps(slim, separators=(",", ":"))

    try:
        raw = chat(system, user)
        llm_out    = parse_json_response(raw)
        reasonings: dict[str, str] = llm_out.get("reasonings", {})
        summary: str = llm_out.get("summary", "Resources ranked by flood emergency suitability.")
    except Exception:
        reasonings = {}
        summary    = "Resources ranked by flood emergency suitability."

    # ── Assemble final output ─────────────────────────────────────────────────
    top_ids = {rid for ids in top_by_category.values() for rid in ids}
    ranked_resources = [
        {
            "id":            r["id"],
            "overall_score": r["overall_score"],
            "recommended":   r["id"] in top_ids,
            "reasoning":     reasonings.get(
                r["id"],
                f"Score {r['overall_score']:.2f} based on safety, availability, and distance.",
            ),
        }
        for r in scored
    ]

    return {
        "ranked_resources": ranked_resources,
        "top_by_category":  top_by_category,
        "summary":          summary,
    }


# ── Step 6 — response_formatter_step (Python) ────────────────────────────────

def response_formatter_step(
    resources: list[dict[str, Any]],
    safety_map: dict[str, dict],
    availability_map: dict[str, dict],
    synthesis: dict[str, Any],
) -> dict[str, Any]:

    if synthesis is None:
        synthesis = _fallback_synthesis(resources)

    resource_lookup  = {r["id"]: r for r in resources}
    ranked_raw       = synthesis.get("ranked_resources", [])
    top_by_category  = synthesis.get("top_by_category", {"hospital": [], "shelter": [], "food": []})

    ranked_resources = []

    for item in ranked_raw:
        rid  = item.get("id")
        base = resource_lookup.get(rid, {})

        ranked_resources.append({
            "id":             rid,
            "name":           base.get("name", "Unknown"),
            "type":           base.get("category", "unknown"),
            "lat":            base.get("lat", 0),
            "lng":            base.get("lng", 0),
            "distance_miles": base.get("distance_miles", 0),
            "overall_score":  item.get("overall_score", 0),
            "status":         availability_map.get(rid, {}).get(
                                  "status", base.get("status", "unknown")),
            "reasoning":      item.get("reasoning", ""),
        })

    ranked_resources.sort(key=lambda x: x["overall_score"], reverse=True)

    def build_top(category: str) -> list[dict]:
        results = []
        for rid in top_by_category.get(category, []):
            ranked_item = next((r for r in ranked_resources if r["id"] == rid), None)
            if resource_lookup.get(rid) and ranked_item:
                results.append(ranked_item)
        return results

    return {
        "recommended_resources": {
            "hospital": build_top("hospital"),
            "shelter":  build_top("shelter"),
            "food":     build_top("food"),
        },
        "ranked_resources": ranked_resources,
        "summary":          synthesis.get("summary", ""),
        "generated_at":     datetime.now(timezone.utc).isoformat(),
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
    """
    # ── Step 1: collect raw data (Python, no LLM) ────────────────────────────
    resources = resource_collection_step(lat, lng)

    if not resources:

        return {
            "recommended_resources": {"hospital": [], "shelter": [], "food": []},
            "ranked_resources":      [],
            "summary":               "No emergency resources found near this location.",
            "generated_at":          datetime.now(timezone.utc).isoformat(),

        }
        _save_agent_response(result)
        return result

    # ── Steps 2 + 3 + 4: safety (LLM), availability (LLM), distance (Python)
    # All three are independent — run them concurrently.
    with ThreadPoolExecutor(max_workers=3) as executor:
        safety_future       = executor.submit(resource_safety_agent, resources)
        availability_future = executor.submit(availability_agent, resources)
        distance_future     = executor.submit(distance_ranking_step, resources, lat, lng)

        safety_result       = safety_future.result()
        availability_result = availability_future.result()
        resources           = distance_future.result()

    safety_map: dict[str, dict] = {
        r["id"]: r for r in safety_result.get("resources", [])
    }
    availability_map: dict[str, dict] = {
        r["id"]: r for r in availability_result.get("resources", [])
    }

    # ── Step 5: synthesis (Python scores + LLM reasoning) ────────────────────
    synthesis = resource_synthesis_agent(resources, safety_map, availability_map)

    # ── Step 6: format final output (Python) ─────────────────────────────────
    final = response_formatter_step(resources, safety_map, availability_map, synthesis)

    return {**final}

