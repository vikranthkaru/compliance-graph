from services.salesforce_service import fetch_shipment_context
def get_static_shipment_event():
    return {
        "eventType": "SHIPMENT_COMPLIANCE_REQUESTED",
        "eventId": "EVT-000000",
        "shipmentId": "a00g500000jefP8AAI",
        "shipmentNumber": "SHP-000000",
        "triggeredBy": "005XXXXXXXXXXXX",
        "triggeredAt": "2026-07-01T10:30:00Z",
        "reason": "Shipment submitted for compliance review"
    }

def handle_shipment_event() -> dict:
    event = get_static_shipment_event()

    shipment_id = event.get("shipmentId")

    if not shipment_id:
        return {
            "status": "rejected",
            "reason": "shipmentId is required"
        }

    shipment_context = fetch_shipment_context(shipment_id)

    return {
        "status": "shipment_context_fetched",
        "event": event,
        "shipmentContext": shipment_context
    }

def route_event_to_agent(event_result: dict) -> dict:
    shipment_context = event_result.get("shipmentContext")

    if not shipment_context:
        return {
            "status": "routing_failed",
            "reason": "shipmentContext is missing",
            "targetAgent": None
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
            "reason": "Shipment requires compliance processing",
            "initialState": {
                "event": event_result.get("event"),
                "shipment_context": shipment_context,
                "currentStep": "fetch_shipment_data"
            }
        }

    return {
        "status": "no_route_found",
        "targetAgent": None,
        "reason": f"No agent route for shipmentStatus={shipment_status}, complianceStatus={compliance_status}"
    }
