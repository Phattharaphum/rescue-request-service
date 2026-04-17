import json
import uuid
from datetime import datetime, timezone

import boto3

from src.shared.config import (
    AWS_ENDPOINT_URL,
    AWS_REGION,
    PRIORITIZATION_COMMANDS_TOPIC_ARN,
    PRIORITIZATION_REEVALUATE_TOPIC_ARN,
    STAGE,
)
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _get_sns_client():
    kwargs = {"region_name": AWS_REGION}
    if STAGE == "local" and AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = AWS_ENDPOINT_URL
    return boto3.client("sns", **kwargs)


def publish_prioritization_command(body: dict, trace_id: str | None = None) -> dict | None:
    return _publish_message(
        topic_arn=PRIORITIZATION_COMMANDS_TOPIC_ARN,
        message_type="RescueRequestPrioritizeCommand",
        body=body,
        trace_id=trace_id,
    )


def publish_prioritization_re_evaluation(
    body: dict,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> dict | None:
    return _publish_message(
        topic_arn=PRIORITIZATION_REEVALUATE_TOPIC_ARN,
        message_type="RescueRequestReEvaluateEvent",
        body=body,
        correlation_id=correlation_id,
        trace_id=trace_id,
    )


def _publish_message(
    topic_arn: str,
    message_type: str,
    body: dict,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> dict | None:
    if not topic_arn:
        logger.warning("Prioritization topic ARN not configured for %s", message_type)
        return None

    header = {
        "messageType": message_type,
        "messageId": str(uuid.uuid4()),
        "sentAt": datetime.now(timezone.utc).isoformat(),
        "traceId": trace_id or str(uuid.uuid4()),
        "version": "1",
    }
    if correlation_id:
        header["correlationId"] = correlation_id

    message = json.dumps({"header": header, "body": body}, default=str)
    client = _get_sns_client()
    message_attributes = {
        "messageType": {"DataType": "String", "StringValue": message_type},
        "version": {"DataType": "String", "StringValue": "1"},
    }
    if correlation_id:
        message_attributes["correlationId"] = {"DataType": "String", "StringValue": correlation_id}

    client.publish(
        TopicArn=topic_arn,
        Message=message,
        MessageAttributes=message_attributes,
    )
    logger.info("Published prioritization message %s", message_type)
    return header
