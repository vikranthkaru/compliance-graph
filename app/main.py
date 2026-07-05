from langgraph.types import Command

from app.routes.events import handle_shipment_event, route_event_to_agent
from agents.compliance_agent.graph import build_compliance_graph


def resume_graph(graph, config, resume_payload):
    return graph.invoke(
        Command(resume=resume_payload),
        config=config,
    )


def main():
    result = handle_shipment_event()
    route_result = route_event_to_agent(result)

    if route_result.get("targetAgent") != "compliance_agent":
        print("No compliance agent route found.")
        return

    initial_state = route_result["initialState"]

    shipment = initial_state["shipment_context"]["shipment"]

    config = {
        "configurable": {
            "thread_id": shipment["shipmentId"]
        }
    }

    compliance_graph = build_compliance_graph()

    result = compliance_graph.invoke(
        initial_state,
        config=config,
    )

    print("===== FIRST RUN =====")
    print(result)

    if "__interrupt__" in result:

        resume_payload = {
            result["__interrupt__"][0].id:
                "India export license verified.",
            result["__interrupt__"][1].id:
                "UAE transit approved.",
            result["__interrupt__"][2].id:
                "Germany import permit will be uploaded.",
        }

        result = resume_graph(
            compliance_graph,
            config,
            resume_payload,
        )

        print("===== AFTER RESUME =====")
        print(result)


if __name__ == "__main__":
    main()
