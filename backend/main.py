import json

from graph import graph
from services.mock_data_service import get_mock_environmental_data, get_mock_location
from state import FloodState

_DIVIDER = "=" * 60
_THIN = "-" * 60


def build_initial_state() -> FloodState:
    """Assemble the starting state from mock data services."""
    return {
        "location": get_mock_location(),
        "environmental_data": get_mock_environmental_data(),
        "risk": {},
        "resources": {},
        "route": {},
        "guidance": "",
        "debug_steps": [],
    }


def _print_section(title: str, body: str) -> None:
    print(f"\n{_DIVIDER}")
    print(f"  {title}")
    print(_DIVIDER)
    print(body)


def main() -> None:
    print(f"\n{'#' * 60}")
    print("  FloodSentinel — Multi-Agent Pipeline Demo")
    print(f"{'#' * 60}")

    initial = build_initial_state()
    print(f"\n[INPUT] Location     : {initial['location']['city']}, {initial['location']['state']}")
    print(f"[INPUT] Rain forecast : {initial['environmental_data']['rain_forecast_inches']} inches")
    print(f"[INPUT] Water level   : {initial['environmental_data']['water_level_status']} ({initial['environmental_data']['water_level_trend']})")
    print(f"[INPUT] Weather alert : {initial['environmental_data']['weather_alert']}")
    print(f"\nRunning agents...")

    final = graph.invoke(initial)

    # ── Guidance ──────────────────────────────────────────────
    _print_section("FINAL GUIDANCE (user-facing)", final["guidance"])

    # ── Risk ──────────────────────────────────────────────────
    risk = final["risk"]
    _print_section(
        "RISK ASSESSMENT",
        f"  Risk level         : {risk.get('risk_level', 'N/A').upper()}\n"
        f"  Confidence         : {risk.get('confidence', 'N/A')}\n"
        f"  Recommended action : {risk.get('recommended_action', 'N/A')}\n"
        f"\n  Escalator  → {risk.get('escalator_reasoning', '')}\n"
        f"  Skeptic    → {risk.get('skeptic_reasoning', '')}\n"
        f"  Summary    → {risk.get('final_reasoning_summary', '')}",
    )

    # ── Top Resource ──────────────────────────────────────────
    top = final["resources"].get("top_resource", {})
    _print_section(
        "TOP RESOURCE",
        f"  Name     : {top.get('name', 'N/A')}\n"
        f"  Type     : {top.get('resource_type', 'N/A')}\n"
        f"  Address  : {top.get('address', 'N/A')}\n"
        f"  Distance : {top.get('distance_miles', 'N/A')} miles\n"
        f"  Safety   : {top.get('safety_score', 'N/A')}/100\n"
        f"  Score    : {top.get('score', 'N/A')} pts\n"
        f"\n  Why → {final['resources'].get('ranking_reason', '')}",
    )

    # ── Route ─────────────────────────────────────────────────
    route = final["route"]
    avoid_str = ", ".join(route.get("avoid", [])) or "none"
    _print_section(
        "ROUTE RECOMMENDATION",
        f"  Route type  : {route.get('route_type', 'N/A')}\n"
        f"  Selected    : {route.get('selected_route_name', 'N/A')}\n"
        f"  ETA         : {route.get('estimated_time', 'N/A')}\n"
        f"  Evacuation  : {'YES' if route.get('is_evacuation_recommended') else 'No'}\n"
        f"  Avoid       : {avoid_str}\n"
        f"\n  Reasoning → {route.get('route_reasoning', '')}",
    )

    # ── Debug steps ───────────────────────────────────────────
    _print_section("DEBUG — AGENT PIPELINE STEPS", "")
    for i, step in enumerate(final["debug_steps"], start=1):
        print(f"  {i}. {step}")

    # ── Full JSON (for devs) ───────────────────────────────────
    print(f"\n{_DIVIDER}")
    print("  FULL STATE (JSON)")
    print(_DIVIDER)
    print(json.dumps(final, indent=2))
    print(f"\n{'#' * 60}\n")


if __name__ == "__main__":
    main()
