import json
from typing import Any


def parse_prioritization_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = _load_json(record.get("body"))

    if isinstance(payload, dict) and payload.get("Type") == "Notification" and "Message" in payload:
        message = _load_json(payload.get("Message"))
        if isinstance(message, dict) and "header" in message and "body" in message:
            extracted_header = _extract_header_from_sns_notification(payload)
            merged_header = dict(extracted_header)
            merged_header.update(message.get("header") or {})
            return {
                "header": merged_header,
                "body": message.get("body"),
            }
        return {
            "header": _extract_header_from_sns_notification(payload),
            "body": message,
        }

    if isinstance(payload, dict) and "header" in payload and "body" in payload:
        return payload

    return {
        "header": _extract_header_from_sqs_record(record),
        "body": payload,
    }


def _extract_header_from_sns_notification(notification: dict[str, Any]) -> dict[str, Any]:
    attributes = notification.get("MessageAttributes") or {}
    topic_arn = notification.get("TopicArn")
    return {
        "messageId": notification.get("MessageId"),
        "messageType": _get_attribute_value(attributes.get("messageType")),
        "correlationId": _get_attribute_value(attributes.get("correlationId")),
        "sentAt": notification.get("Timestamp"),
        "version": _get_attribute_value(attributes.get("version")) or "1",
        "topicArn": topic_arn,
        "channel": _infer_channel(topic_arn),
    }


def _extract_header_from_sqs_record(record: dict[str, Any]) -> dict[str, Any]:
    attributes = record.get("messageAttributes") or {}
    return {
        "messageId": record.get("messageId"),
        "messageType": _get_attribute_value(attributes.get("messageType")),
        "correlationId": _get_attribute_value(attributes.get("correlationId")),
        "sentAt": _get_attribute_value(attributes.get("sentAt")),
        "version": _get_attribute_value(attributes.get("version")) or "1",
    }


def _infer_channel(topic_arn: Any) -> str | None:
    if not isinstance(topic_arn, str):
        return None
    if "rescue-prioritization-created-v1" in topic_arn:
        return "rescue.prioritization.created.v1"
    if "rescue-prioritization-updated-v1" in topic_arn:
        return "rescue.prioritization.updated.v1"
    return None


def _get_attribute_value(attribute: Any) -> Any:
    if isinstance(attribute, dict):
        return attribute.get("Value") or attribute.get("StringValue")
    return attribute


def _load_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
