from typing import Any, TypedDict


class FloodState(TypedDict):
    """Shared state passed between every LangGraph node."""

    location: dict[str, Any]
    environmental_data: dict[str, Any]
    risk: dict[str, Any]
    resources: dict[str, Any]
    route: dict[str, Any]
    guidance: str
    debug_steps: list[str]
