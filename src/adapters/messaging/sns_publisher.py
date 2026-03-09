import json

import boto3

from src.adapters.messaging.event_envelope_builder import build_envelope
from src.shared.config import AWS_REGION, DYNAMODB_ENDPOINT, SERVICE_NAME, SNS_TOPIC_ARN, STAGE
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _get_sns_client():
    kwargs = {"region_name": AWS_REGION}
    if STAGE == "local" and DYNAMODB_ENDPOINT:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
    return boto3.client("sns", **kwargs)


def publish_event(
    event_type: str,
    body: dict,
    partition_key: str,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    try:
        envelope = build_envelope(
            event_type=event_type,
            body=body,
            partition_key=partition_key,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        message = json.dumps(envelope, default=str)
        message_attributes = {
            "eventType": {"DataType": "String", "StringValue": event_type},
            "schemaVersion": {"DataType": "String", "StringValue": "1.0"},
            "producer": {"DataType": "String", "StringValue": SERVICE_NAME},
        }

        if SNS_TOPIC_ARN:
            client = _get_sns_client()
            client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                MessageAttributes=message_attributes,
            )
            logger.info(f"Published event {event_type} for {partition_key}")
        else:
            logger.warning(f"SNS_TOPIC_ARN not set, skipping publish for {event_type}")
    except Exception:
        logger.exception(f"Failed to publish event {event_type}")
