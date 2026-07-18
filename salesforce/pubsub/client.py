import grpc

from salesforce.connection import (
    SalesforcePubSubConnection,
    get_salesforce_pubsub_connection,
)
from salesforce.pubsub import pubsub_api_pb2_grpc


PUBSUB_ENDPOINT = "api.pubsub.salesforce.com:7443"


class SalesforcePubSubClient:
    """
    Creates the secure gRPC channel and Pub/Sub API stub.
    """

    def __init__(self) -> None:
        self.connection: SalesforcePubSubConnection = (
            get_salesforce_pubsub_connection()
        )

        self.channel = grpc.secure_channel(
            PUBSUB_ENDPOINT,
            grpc.ssl_channel_credentials(),
        )

        self.stub = pubsub_api_pb2_grpc.PubSubStub(
            self.channel
        )

    @property
    def metadata(self) -> tuple[tuple[str, str], ...]:
        """
        Returns the authentication metadata required by
        Salesforce Pub/Sub API RPC calls.
        """

        return (
            ("accesstoken", self.connection.access_token),
            ("instanceurl", self.connection.instance_url),
            ("tenantid", self.connection.tenant_id),
        )

    def close(self) -> None:
        """
        Closes the gRPC channel.
        """

        self.channel.close()