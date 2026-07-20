import io
import json
import logging
import threading
import time
from collections.abc import Iterator

import avro.io
import avro.schema
import grpc

from salesforce.pubsub import pubsub_api_pb2
from salesforce.pubsub.client import SalesforcePubSubClient
from salesforce.pubsub.event_router import route_event

logger = logging.getLogger(__name__)

PLATFORM_EVENT_TOPIC = "/event/Shipment_Compliance_Event__e"

# Initial value 1 allows the first FetchRequest to be sent.
semaphore = threading.Semaphore(1)


def fetch_request_stream(
    topic: str,
) -> Iterator[pubsub_api_pb2.FetchRequest]:
    """
    Creates the bidirectional FetchRequest stream.

    A new event is requested only after the previous event
    has been received and processed.
    """

    while True:
        semaphore.acquire()

        yield pubsub_api_pb2.FetchRequest(
            topic_name=topic,
            replay_preset=pubsub_api_pb2.ReplayPreset.LATEST,
            num_requested=1,
        )


def decode_event(schema_json: str, payload: bytes) -> dict:
    """
    Decodes an Avro-encoded Salesforce event payload.
    """

    schema = avro.schema.parse(schema_json)

    buffer = io.BytesIO(payload)
    decoder = avro.io.BinaryDecoder(buffer)
    reader = avro.io.DatumReader(schema)

    return reader.read(decoder)


def subscribe_to_compliance_events() -> None:
    """
    Subscribes to the Shipment Compliance Platform Event
    and routes decoded event payloads.
    """

    client = SalesforcePubSubClient()

    latest_replay_id: bytes | None = None

    try:
        logger.info(
            "Subscribing to Salesforce topic: %s",
            PLATFORM_EVENT_TOPIC,
        )

        subscription_stream = client.stub.Subscribe(
            fetch_request_stream(PLATFORM_EVENT_TOPIC),
            metadata=client.metadata,
        )

        for fetch_response in subscription_stream:
            if fetch_response.events:
                logger.info(
                    "Number of events received: %s",
                    len(fetch_response.events),
                )

                for consumer_event in fetch_response.events:
                    event = consumer_event.event

                    schema_response = client.stub.GetSchema(
                        pubsub_api_pb2.SchemaRequest(
                            schema_id=event.schema_id,
                        ),
                        metadata=client.metadata,
                    )

                    decoded_payload = decode_event(
                        schema_json=schema_response.schema_json,
                        payload=event.payload,
                    )

                    routed_event = route_event(decoded_payload)
                    logger.info(
                        "Routed event: %s",
                        json.dumps(
                            routed_event,
                            indent=2,
                            default=str,
                        ),
                    )

                    latest_replay_id = consumer_event.replay_id

                # Request the next event only after processing
                # the current event.
                semaphore.release()

            else:
                logger.info(
                    "[%s] Subscription is active.",
                    time.strftime(
                        "%b %d, %Y %I:%M %p %Z",
                    ),
                )

            if fetch_response.latest_replay_id:
                latest_replay_id = (
                    fetch_response.latest_replay_id
                )

    except grpc.RpcError as exc:
        logger.exception(
            "Salesforce Pub/Sub subscription failed. "
            "Status=%s Details=%s",
            exc.code(),
            exc.details(),
        )
        raise

    except KeyboardInterrupt:
        logger.info("Subscription stopped by the user.")

    finally:
        if latest_replay_id:
            logger.info(
                "Latest replay ID received: %s",
                latest_replay_id.hex(),
            )

        client.close()


def start() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        force=True,
    )

    subscribe_to_compliance_events()


def main() -> None:
    start()


if __name__ == "__main__":
    main()