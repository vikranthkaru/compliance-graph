import logging
from typing import Any
from simple_salesforce import Salesforce
from config.loader import load_yaml
from config.security import get_private_key_file

logger = logging.getLogger(__name__)

def get_salesforce_cloud_connection() -> Salesforce:
    """
    Creates and returns an authenticated Salesforce Data Cloud connection.
    """
    config = load_yaml("config.yaml")
    sf_config = config["salesforce"]
    try:
        sf = Salesforce(
        consumer_key=sf_config["connected_app"]["client_id"],
        username=sf_config["username"],
        privatekey_file=get_private_key_file()
        )
        return sf
    except Exception as e:
        logger.exception(
            "Salesforce Core connection establishment failed"
        )
        raise


def fetch_shipment_context(shipment_id: str) -> dict:
    """
    Temporary mock function.
    Later this will call Salesforce API using shipment_id.
    For now, it returns hardcoded shipment context JSON.
    """
    sf = get_salesforce_cloud_connection()

    
    try:
        response = sf.apexecute(f"shipment/{shipment_id}", method="GET")
        print(f"Shipment context fetched: {response}")
        return response
        
    except Exception as e:
        print(f"Error fetching shipment from Salesforce: {e}")
        return {}

def save_route_check(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Sends route-level compliance data to the Apex REST endpoint.

    Expected payload shape:
    {
        "identifier": "ROUTE_COMPLIANCE",
        "routeCheck": {
            ...
        }
    }
    """
    sf = get_salesforce_cloud_connection()
    if isinstance(sf, Exception):
        return {
            "success": False,
            "action": "Failed",
            "recordId": None,
            "message": str(sf),
        }

    try:
        response = sf.apexecute(
            "shipment/",
            method="POST",
            data=payload,
        )

        if not isinstance(response, dict):
            return {
                "success": False,
                "action": "Failed",
                "recordId": None,
                "message": f"Unexpected Salesforce response: {response}",
            }

        return response

    except Exception as exc:
        print(f"Error saving route compliance check: {exc}")

        return {
            "success": False,
            "action": "Failed",
            "recordId": None,
            "message": str(exc),
        }