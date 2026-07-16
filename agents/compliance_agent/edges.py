from langgraph.types import Send

from agents.compliance_agent.state import ComplianceState


def route_validation_edge(state: ComplianceState) -> str:
    if state.get("errors"):
        return "end"

    return "continue"


def route_splitter(state: ComplianceState):
    """
    Fan-out node.

    Creates one isolated RouteComplianceWorkerState
    for every country/route in the regulation search plan.
    """

    shipment_context = state["shipment_context"]

    regulation_requirements = state["regulation_search_plan"][
        "regulation_requirements"
    ]

    print(
        f"Route splitter started for "
        f"{len(regulation_requirements)} routes"
    )

    def normalize(value: str | None) -> str:
        return (value or "").strip().lower()
    
    routes = shipment_context.get("route", [])

    def find_route_id(
        country: str,
        route_type: str,
    ) -> str | None:
        for route in routes:
            if (
                normalize(route.get("country")) == normalize(country)
                and 
                normalize(route.get("routeType")) == normalize(route_type)
            ):
                return route.get("routeId")

        return None

    sends = []

    for requirement in regulation_requirements:
        route_id = find_route_id(
            country=requirement["country"],
            route_type=requirement["route_type"],
        )

        if route_id is None:
            raise ValueError(
                "Unable to match Salesforce route for "
                f"{requirement['country']} / "
                f"{requirement['route_type']}"
            )

        sends.append(
            Send(
                "compliance_parallel_subgraph",
                {
                    "shipment_id": shipment_context[
                        "shipment"
                    ]["shipmentId"],
                    "shipment_context": shipment_context,
                    "route_id": route_id,
                    "regulation_requirement": requirement,
                    "company_policy_context": [],
                    "government_regulation_context": [],
                    "internal_policy_fetched": False,
                    "external_policy_fetched": False,
                    "route_decision": None,
                    "human_feedback": [],
                    "iteration_count": 0,
                    "errors": [],
                },
            )
        )
    return sends