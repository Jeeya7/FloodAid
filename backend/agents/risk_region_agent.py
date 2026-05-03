# risk_region_agent.py
#
# Multi-step flood-risk reasoning pipeline.
#
# Flow:
#   1. Python calls the tools/services to collect raw environmental data.
#   2. data_quality_agent  — checks data completeness and flags issues.
#   3. hydrology_agent     — analyzes water-level, streamflow, and trend risk.
#   4. weather_risk_agent  — analyzes rainfall, forecast, and alert risk.
#   5. risk_synthesis_agent — combines all evidence into a final risk verdict.
#   6. response_formatter_agent — shapes everything into frontend-ready JSON.
#
# LLM: NVIDIA via OpenRouter (one call per sub-agent, per region).
# The LLM never calls external APIs — it only reasons over data Python fetched.

import json
from datetime import datetime, timezone
from typing import Any

from openrouter_client import chat, parse_json_response
from tools.risk_region_tools import (
    DEFAULT_BOUNDS,
    get_gauges_by_bounds_tool,
    get_streamflow_context_tool,
    get_usgs_water_data_tool,
    get_weather_context_tool,
    create_bounds_tool
)

MAX_GAUGES = 3

NEWPORT_BOUNDS = {
    "south": 44.55,
    "north": 44.75,
    "west": -124.10,
    "east": -123.80,
}


# ── Fallback templates (used when one LLM step fails) ────────────────────────

def _fallback_data_quality() -> dict[str, Any]:
    return {
        "usable": True,
        "missing_fields": [],
        "data_warnings": ["Data quality check unavailable — using raw data as-is."],
        "confidence_modifier": 0.7,
    }


def _fallback_hydrology() -> dict[str, Any]:
    return {
        "hydrology_risk": "moderate",
        "hydrology_evidence": ["Hydrology analysis unavailable."],
        "trend": "unknown",
        "reasoning_summary": "Hydrology agent failed; defaulting to moderate risk.",
    }


def _fallback_weather() -> dict[str, Any]:
    return {
        "weather_risk": "moderate",
        "weather_evidence": ["Weather analysis unavailable."],
        "alert_level": "none",
        "reasoning_summary": "Weather agent failed; defaulting to moderate risk.",
    }


def _fallback_synthesis(hydro: dict, weather: dict) -> dict[str, Any]:
    # Pick the worse of the two available risk levels
    order = ["low", "moderate", "high", "critical"]
    level = max(
        hydro.get("hydrology_risk", "moderate"),
        weather.get("weather_risk", "moderate"),
        key=lambda x: order.index(x) if x in order else 1,
    )
    return {
        "risk_level": level,
        "confidence": 0.5,
        "reasoning_summary": "Synthesis agent failed; risk estimated from sub-agent outputs.",
        "recommended_action": "Monitor conditions and follow local emergency guidance.",
    }


# ── Sub-agent functions ───────────────────────────────────────────────────────

def data_quality_agent(raw_packet: dict[str, Any]) -> dict[str, Any]:
    """
    Inspect the raw USGS / Water Services / Weather data for completeness.
    Returns a quality verdict the other agents use to weight their confidence.
    """
    system = (
        "You are a data quality checker for a flood-safety system. "
        "Examine the provided environmental data packet. "
        "Identify missing, suspicious, or stale fields. "
        "Return ONLY valid JSON matching this schema — no markdown:\n"
        '{"usable":true,"missing_fields":[],"data_warnings":[],"confidence_modifier":1.0}'
    )
    user = f"Data packet:\n{json.dumps(raw_packet, separators=(',', ':'))}"

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        return {**_fallback_data_quality(), "data_warnings": [f"Data quality check error: {exc}"]}


def hydrology_agent(raw_packet: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze water-level, streamflow, discharge, and trends.
    Uses the data quality modifier to adjust confidence.
    """
    system = (
        "You are a hydrology risk analyst for a flood-safety system. "
        "Analyze the USGS and water services data. Focus on: gage height vs flood stage, "
        "streamflow percentile, water level trend, and anomaly level. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"hydrology_risk":"low|moderate|high|critical",'
        '"hydrology_evidence":[],"trend":"rising|stable|falling|unknown",'
        '"reasoning_summary":"string"}'
    )
    user = (
        f"USGS data: {json.dumps(raw_packet.get('usgs', {}), separators=(',', ':'))}\n"
        f"Streamflow: {json.dumps(raw_packet.get('water_services', {}), separators=(',', ':'))}\n"
        f"Data quality confidence modifier: {quality.get('confidence_modifier', 1.0)}"
    )

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        return {**_fallback_hydrology(), "hydrology_evidence": [f"Hydrology agent error: {exc}"]}


def weather_risk_agent(raw_packet: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze rainfall forecasts, current precipitation, and NWS alerts.
    """
    system = (
        "You are a weather risk analyst for a flood-safety system. "
        "Analyze the weather forecast data. Focus on: active flood watch/warning, "
        "rain forecast totals, short-term rainfall rate, and storm probability. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"weather_risk":"low|moderate|high|critical",'
        '"weather_evidence":[],"alert_level":"none|watch|warning|emergency",'
        '"reasoning_summary":"string"}'
    )
    user = (
        f"Weather data: {json.dumps(raw_packet.get('weather', {}), separators=(',', ':'))}\n"
        f"Data quality confidence modifier: {quality.get('confidence_modifier', 1.0)}"
    )

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        return {**_fallback_weather(), "weather_evidence": [f"Weather agent error: {exc}"]}


def risk_synthesis_agent(
    gauge: dict[str, Any],
    quality: dict[str, Any],
    hydro: dict[str, Any],
    weather: dict[str, Any],
) -> dict[str, Any]:
    """
    Combine data quality, hydrology risk, and weather risk into a final verdict.
    """
    system = (
        "You are a flood risk synthesis analyst. "
        "You will receive outputs from three specialist agents. "
        "Combine the evidence and determine the final flood risk for this location. "
        "Consider whether evidence sources agree or conflict. "
        "Apply the confidence modifier from data quality. "
        "Return ONLY valid JSON — no markdown:\n"
        '{"risk_level":"low|moderate|high|critical","confidence":0.0,'
        '"reasoning_summary":"string","recommended_action":"string"}'
    )
    user = (
        f"Location: {gauge['name']} \n"
        f"Data quality: {json.dumps(quality, separators=(',', ':'))}\n"
        f"Hydrology: {json.dumps(hydro, separators=(',', ':'))}\n"
        f"Weather: {json.dumps(weather, separators=(',', ':'))}"
    )

    try:
        raw = chat(system, user)
        return parse_json_response(raw)
    except Exception as exc:
        result = _fallback_synthesis(hydro, weather)
        result["reasoning_summary"] += f" (Synthesis error: {exc})"
        return result


def response_formatter_agent(
    gauge: dict[str, Any],
    quality: dict[str, Any],
    hydro: dict[str, Any],
    weather: dict[str, Any],
    synthesis: dict[str, Any],
) -> dict[str, Any]:
    """
    Shape all agent outputs into the final frontend-ready region object.
    Color mapping: low=green, moderate=yellow, high=orange, critical=red.
    """
    color_map = {"low": "green", "moderate": "yellow", "high": "orange", "critical": "red"}
    risk_level = synthesis.get("risk_level", "moderate")

    return {
        "area_id": gauge["site_id"],
        "name": gauge["name"],
        "center": {"lat": gauge["lat"], "lng": gauge["lng"]},
        "risk_level": risk_level,
        "color": color_map.get(risk_level, "yellow"),
        "confidence": synthesis.get("confidence", 0.5),
        "evidence": {
            "data_quality": quality,
            "hydrology": hydro,
            "weather": weather,
        },
        "reasoning_summary": synthesis.get("reasoning_summary", ""),
        "recommended_action": synthesis.get("recommended_action", ""),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def risk_region_agent(lat: float, lng: float, radius_miles: float = 25) -> dict[str, Any]:
    """
    Full multi-step flood risk pipeline.

    1. Python fetches environmental data via tools (no LLM involvement).
    2. Each sub-agent (LLM step) reasons over one slice of the data.
    3. Synthesis combines all evidence into a final verdict per region.
    4. Formatter produces the frontend-ready JSON.
    """
    bounds = create_bounds_tool.invoke({
        "lat": lat,
        "lng": lng,
        "radius_miles": radius_miles,
    })

    # ── Step 1: collect raw data (Python, no LLM) ────────────────────────────
    gauges = get_gauges_by_bounds_tool.invoke({"bounds": bounds})
    gauges = gauges[:MAX_GAUGES]

    environmental_risk_packets: list[dict] = []
    regions: list[dict] = []

    print(f"GAUGE: {gauges}")
    for gauge in gauges:
        sid = gauge["site_id"]
        raw_packet = {
            "usgs":           get_usgs_water_data_tool.invoke({"station_id": sid}),
            "water_services": get_streamflow_context_tool.invoke({"station_id": sid}),
            "weather":        get_weather_context_tool.invoke({"lat": gauge["lat"], "lng": gauge["lng"]}),
        }

        # Store the full packet for transparency
        environmental_risk_packets.append({
            "area_id":    sid,
            "name":       gauge["name"],
            # "river_name": gauge["river_name"],
            "river_name": "",
            "center":     {"lat": gauge["lat"], "lng": gauge["lng"]},
            "raw_packet": raw_packet,
        })


        # ── Steps 2–5: sub-agent reasoning (LLM calls) ───────────────────────
        quality   = data_quality_agent(raw_packet)

        hydro     = hydrology_agent(raw_packet, quality)

        weather   = weather_risk_agent(raw_packet, quality)

        synthesis = risk_synthesis_agent(gauge, quality, hydro, weather)

        # ── Step 6: format ────────────────────────────────────────────────────
        region = response_formatter_agent(gauge, quality, hydro, weather, synthesis)
        regions.append(region)

    # ── Build overall summary (single extra LLM call) ────────────────────────
    summary = _build_summary(regions)

    return {
        "lat": lat,
        "lang": lng,
        "raidus": radius_miles,
        "regions": regions,
        "environmental_risk_packets": environmental_risk_packets,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_summary(regions: list[dict]) -> str:
    """Ask the LLM for a one-sentence overall flood situation summary."""
    if not regions:
        return "No flood risk regions were analyzed."

    brief = [
        {"name": r["name"], "risk": r["risk_level"], "action": r["recommended_action"]}
        for r in regions
    ]
    system = (
        "You are a flood safety communicator. "
        "Write a single short sentence summarizing the overall flood situation across the listed regions. "
        "Be calm and factual. Return only the sentence — no quotes, no markdown."
    )
    user = json.dumps(brief, separators=(",", ":"))

    try:
        return chat(system, user, max_tokens=80).strip()
    except Exception:
        high_count = sum(1 for r in regions if r["risk_level"] in ("high", "critical"))
        return (
            f"Analysis complete: {len(regions)} regions assessed, "
            f"{high_count} with high or critical flood risk."
        )
