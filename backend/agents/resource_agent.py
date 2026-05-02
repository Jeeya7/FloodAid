from services.mock_data_service import get_mock_resources
from services.resource_scoring_service import rank_resources
from state import FloodState


def resource_agent(state: FloodState) -> FloodState:
    """Select and rank nearby resources without using an LLM."""

    resources = get_mock_resources()
    ranked = rank_resources(resources, state["risk"])
    top_resource = ranked[0]

    resources_state = {
        "ranked_resources": ranked,
        "top_resource": top_resource,
        "ranking_reason": (
            "Resources ranked by proximity, type usefulness for current risk level, "
            "and safety score. Shelter gets extra weight under high/moderate risk."
        ),
    }

    debug_steps = state.get("debug_steps", [])
    debug_steps.append(
        f"Resource Agent: fetched {len(ranked)} resources via mock_data_service, "
        f"ranked via resource_scoring_service. "
        f"Top resource → {top_resource['name']} (score={top_resource['score']}, "
        f"type={top_resource['resource_type']}, "
        f"distance={top_resource['distance_miles']} mi)."
    )

    return {
        **state,
        "resources": resources_state,
        "debug_steps": debug_steps,
    }
