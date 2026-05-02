from typing import Any, TypedDict


class FloodState(TypedDict):
    """Shared state passed between every LangGraph node."""

    # ── Original fields ──────────────────────────────────────
    location: dict[str, Any]
    environmental_data: dict[str, Any]
    risk: dict[str, Any]
    resources: dict[str, Any]
    route: dict[str, Any]
    debug_steps: list[str]

    # ── Risk Region Agent fields ──────────────────────────────
    # Optional lat/lng bounding box for the map view.
    # If omitted, risk_region_agent uses the contiguous U.S. as the default.
    map_bounds: dict[str, float]

    # Full environmental data packets for every gauge analysed (all risk levels).
    environmental_risk_packets: list[dict[str, Any]]

    # Only the high/moderate risk areas — sent to the frontend map.
    risk_regions: list[dict[str, Any]]
