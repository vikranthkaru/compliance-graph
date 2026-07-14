from langgraph.types import Send
from agents.compliance_agent.state import ComplianceState

def route_validation_edge(state: ComplianceState):
    if state.get("errors"):
        return "end"

    return "continue"
3

def route_splitter(state: ComplianceState):
    """
    Fan-out node.

    Creates one isolated RouteComplianceWorkerState
    for every country/route in the regulation search plan.
    """
    # Send a separate, isolated WorkerState to each parallel 'analyzer_node'
    shipment_context = state["shipment_context"]

    regulation_requirements = state["regulation_search_plan"][
        "regulation_requirements"
    ]
    print(f'breaker node :: {state}')
    def find_route_id(country: str, route_type: str) -> str | None:
        for route in routes:
            if (
                route.get("country") == country
                and route.get("routeType") == route_type
            ):
                return route.get("routeId")
        return None
        
    return [
        Send(
            "compliance_parallel_subgraph",
            {
                "shipment_id": shipment_context["shipment"]["shipmentId"],
                "shipment_context": shipment_context,

                # "country": requirement["country"],
                # "route_type": requirement["route_type"],

                "route_id": find_route_id(
                    requirement["country"],
                    requirement["route_type"],
                ),

                "regulation_requirement": requirement,

                "company_policy_context": [],
                "government_regulation_context": [],

                "internal_policy_fetched": False,
                "external_policy_fetched": False,

                "route_decision": None,

                "human_feedback": None,
                "iteration_count": 0,

                "errors": [],
            },
        )
        for requirement in regulation_requirements
    ]


