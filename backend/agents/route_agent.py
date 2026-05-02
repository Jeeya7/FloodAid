from services.mock_data_service import get_mock_routes
from services.route_scoring_service import choose_route
from state import FloodState


def route_agent(state: FloodState) -> FloodState:
    """Choose the safest route based on risk and top resource without using an LLM."""

    routes = get_mock_routes()
    top_resource = state["resources"]["top_resource"]
    route = choose_route(routes, state["risk"], top_resource)

    debug_steps = state.get("debug_steps", [])
    debug_steps.append(
        f"Route Agent: evaluated {len(routes)} routes via mock_data_service, "
        f"selected via route_scoring_service. "
        f"Chosen → '{route['selected_route_name']}' ({route['route_type']}), "
        f"ETA={route['estimated_time']}, "
        f"evacuation={route['is_evacuation_recommended']}."
    )

    return {
        **state,
        "route": route,
        "debug_steps": debug_steps,
    }
