from langgraph.types import Command
from app.routes.events import handle_shipment_event, route_event_to_agent
from agents.compliance_agent.graph import build_compliance_graph
from services.salesforce_service import save_route_check

from uuid import uuid4

def resume_graph(graph, config, resume_payload):
    return graph.invoke(
        Command(resume=resume_payload),
        config=config,
    )

from agents.compliance_agent.helpers import helper_stringify_list
def main():
    result = handle_shipment_event()
    route_result = route_event_to_agent(result)

    if route_result.get("targetAgent") != "compliance_agent":
        print("No compliance agent route found.")
        return

    initial_state = route_result["initialState"]

    shipment = initial_state["shipment_context"]["shipment"]
    thread_id = str(uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id
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
        for current_interrupt in result["__interrupt__"]:
            interrupt_payload = current_interrupt.value
            decision = interrupt_payload["current_decision"]

            update_response = save_route_check(
                {
                    "identifier": "ROUTE_COMPLIANCE",
                    "routeCheck": {
                        "operation": "Update_Current_Iteration",
                        "shipmentRouteId": interrupt_payload[
                            "shipment_route_id"
                        ],
                        "country": interrupt_payload["country"],
                        "routeType": interrupt_payload["route_type"],
                        "iterationNumber": interrupt_payload[
                            "iteration_number"
                        ],
                        "threadId": interrupt_payload["thread_id"],
                        "interruptId": current_interrupt.id,
                        "complianceStatus": "Review Required",
                        "riskLevel": decision["risk_level"],
                        "confidenceScore": decision[
                            "confidence_score"
                        ],
                        "missingDocuments": helper_stringify_list(
                            decision.get("missing_documents", [])
                        ),
                        "regulationSummary": decision["summary"],
                        "companyPolicyResult": helper_stringify_list(
                            decision.get("policy_conflicts", [])
                        ),
                        "evidenceReference": helper_stringify_list(
                            decision.get("evidence_sources", [])
                        ),
                        "recommendedAction": decision[
                            "recommended_action"
                        ],
                    },
                }
            )
            if not update_response.get("success"):
                print(
                    "Unable to update Salesforce review record: "
                    f"{update_response.get('message')}"
                )
            else:
                print(
                    f"Salesforce route check updated: "
                    f"{update_response.get('recordId')}"
                )
        # resume_payload = {}

        # for intr in result["__interrupt__"]:
        #     country = intr.value["country"]

        #     if country == "India":
        #         resume_payload[intr.id] = "India export license verified."
        #     elif country == "UAE":
        #         resume_payload[intr.id] = "UAE transit approved."
        #     elif country == "Germany":
        #         resume_payload[intr.id] = "Germany import permit will be uploaded."

        # result = resume_graph(
        #     compliance_graph,
        #     config,
        #     resume_payload,
        # )

        # print("===== AFTER RESUME =====")
        # print(result)



if __name__ == "__main__":
    main()
