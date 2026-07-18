from typing import Any

SUPPORTED_EVENT_TYPES = {
    "COMPLIANCE_REQUESTED",
    "ROUTE_COMPLIANCE_RETRIGGERED"
}

from app.routes.compliance_event_handler import (handle_new_compliance_event, handle_resume_compliance_event)
def route_event(event_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Validates and routes a decoded Salesforce Platform Event.
    """

    event_type = event_payload.get("EventType__c")
    shipment_id = event_payload.get("ShipmentId__c")

    if not event_type:
        raise ValueError("EventType__c is missing from the event payload.")

    if not shipment_id:
        raise ValueError("ShipmentId__c is missing from the event payload.")

    if event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported event type received: {event_type}"
        )

    if event_type == "COMPLIANCE_REQUESTED":
        handle_new_compliance_event(event_payload)
        return
    
    if event_type == "ROUTE_COMPLIANCE_RETRIGGERED":
        handle_resume_compliance_event(event_payload)
        return

    raise ValueError(f"Unsupported event type: {event_type}")
        