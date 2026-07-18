from typing import Any

from services.salesforce_service import fetch_shipment_context


def handle_shipment_event(
    event_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Validates the received Salesforce event and fetches
    the complete shipment context from Salesforce.
    """

    shipment_id = event_payload.get("ShipmentId__c")

    if not shipment_id:
        return {
            "status": "rejected",
            "reason": "shipment_id is required",
            "event": event_payload,
            "shipmentContext": None,
        }

    shipment_context = fetch_shipment_context(shipment_id)

    if not shipment_context:
        return {
            "status": "rejected",
            "reason": (
                f"Shipment context could not be fetched "
                f"for shipment_id={shipment_id}"
            ),
            "event": event_payload,
            "shipmentContext": None,
        }

    normalized_event = {
        "eventType": event_payload.get("event_type"),
        "eventId": event_payload.get("event_id"),
        "shipmentId": shipment_id,
        "shipmentNumber": event_payload.get(
            "shipment_number"
        ),
        "triggeredBy": event_payload.get("triggered_by"),
        "triggeredAt": event_payload.get("triggered_at"),
        "reason": event_payload.get("reason"),
        "threadId": event_payload.get("thread_id"),
        "interruptId": event_payload.get("interrupt_id"),
        "complianceRouteCheckId": event_payload.get(
            "compliance_route_check_id"
        ),
        "complianceCheckId": event_payload.get(
            "compliance_check_id"
        ),
    }

    return {
        "status": "shipment_context_fetched",
        "event": normalized_event,
        "shipmentContext": shipment_context,
    }


def route_event_to_agent(
    event_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Routes the shipment event to the appropriate agent
    based on the latest Salesforce shipment state.
    """

    if event_result.get("status") != "shipment_context_fetched":
        return {
            "status": "routing_failed",
            "reason": event_result.get(
                "reason",
                "Shipment event processing failed.",
            ),
            "targetAgent": None,
        }

    shipment_context = event_result.get("shipmentContext")

    if not shipment_context:
        return {
            "status": "routing_failed",
            "reason": "shipmentContext is missing",
            "targetAgent": None,
        }

    shipment = shipment_context.get("shipment", {})

    shipment_status = shipment.get("shipmentStatus")
    compliance_status = shipment.get("complianceStatus")

    if (
        shipment_status == "Pending Compliance"
        and compliance_status == "Pending"
    ):
        return {
            "status": "routed",
            "targetAgent": "compliance_agent",
            "reason": (
                "Shipment requires compliance processing"
            ),
            "initialState": {
                "event": event_result.get("event"),
                "shipment_context": shipment_context,
                "currentStep": "fetch_shipment_data",
            },
        }

    return {
        "status": "no_route_found",
        "targetAgent": None,
        "reason": (
            "No agent route found for "
            f"shipmentStatus={shipment_status}, "
            f"complianceStatus={compliance_status}"
        ),
    }