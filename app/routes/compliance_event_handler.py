from uuid import uuid4

from langgraph.types import Command

from agents.compliance_agent.graph import build_compliance_graph
from agents.compliance_agent.helpers import helper_stringify_list
from app.routes.events import (
    handle_shipment_event,
)
from services.salesforce_service import (
    save_route_check,
)


def handle_new_compliance_event(
    event_payload: dict,
) -> dict:
    """
    Starts a brand new compliance workflow.
    """

    shipment_result = handle_shipment_event(event_payload)

    if shipment_result["status"] != "shipment_context_fetched":
        raise RuntimeError(
            shipment_result.get("reason")
        )

    initial_state = {
        "event": shipment_result["event"],
        "shipment_context": shipment_result["shipmentContext"],
    }

    thread_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    graph = build_compliance_graph()

    result = graph.invoke(
        initial_state,
        config=config,
    )

    process_interrupts(
        result=result,
        thread_id=thread_id,
    )

    return result


def handle_resume_compliance_event(
    event_payload: dict,
) -> dict:
    """
    Resumes an interrupted compliance workflow.
    """

    graph = build_compliance_graph()

    thread_id = event_payload["ThreadId__c"]
    interrupt_id = event_payload["InterruptId__c"]

    resume_payload = {
        interrupt_id: event_payload["Reason__c"]
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    result = graph.invoke(
        Command(resume=resume_payload),
        config=config,
    )

    process_interrupts(
        result=result,
        thread_id=thread_id,
    )

    return result


def process_interrupts(
    result: dict,
    thread_id: str,
) -> None:
    """
    Saves every LangGraph interrupt back into Salesforce.
    """

    if "__interrupt__" not in result:
        return

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
                    "threadId": thread_id,
                    "interruptId": current_interrupt.id,
                    "complianceStatus": "Review Required",
                    "riskLevel": decision["risk_level"],
                    "confidenceScore": decision[
                        "confidence_score"
                    ],
                    "missingDocuments": helper_stringify_list(
                        decision.get(
                            "missing_documents",
                            [],
                        )
                    ),
                    "regulationSummary": decision["summary"],
                    "companyPolicyResult": helper_stringify_list(
                        decision.get(
                            "policy_conflicts",
                            [],
                        )
                    ),
                    "evidenceReference": helper_stringify_list(
                        decision.get(
                            "evidence_sources",
                            [],
                        )
                    ),
                    "recommendedAction": decision[
                        "recommended_action"
                    ],
                },
            }
        )

        if not update_response.get("success"):
            raise RuntimeError(
                "Unable to update Salesforce review record: "
                f"{update_response.get('message')}"
            )