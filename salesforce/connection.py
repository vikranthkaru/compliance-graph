from dataclasses import dataclass
from services.salesforce_service import (
    get_salesforce_cloud_connection,
)

from config.loader import load_yaml

@dataclass(frozen=True)
class SalesforcePubSubConnection:
    access_token: str
    instance_url: str
    tenant_id: str


def get_salesforce_pubsub_connection() -> SalesforcePubSubConnection:
    """
    Reuses the existing JWT-authenticated Salesforce session
    for Pub/Sub API authentication.
    """

    sf = get_salesforce_cloud_connection()
    config = load_yaml("config.yaml")
    salesforce_config = config.get("salesforce", {})
    tenant_id = salesforce_config.get("org_id")

    if not tenant_id:
        raise RuntimeError(
            "salesforce.org_id is missing in config.yaml."
        )

    return SalesforcePubSubConnection(
        access_token=sf.session_id,
        instance_url=f"https://{sf.sf_instance}",
        tenant_id=tenant_id,
    )