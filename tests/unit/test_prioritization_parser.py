import json

from src.adapters.messaging.prioritization_parser import parse_prioritization_record


def test_parses_sns_wrapped_created_topic_and_preserves_channel():
    record = {
        "messageId": "sqs-record-1",
        "body": json.dumps({
            "Type": "Notification",
            "MessageId": "sns-message-1",
            "TopicArn": "arn:aws:sns:ap-southeast-1:123456789012:rescue-prioritization-created-v1-dev",
            "Timestamp": "2026-04-18T00:05:00+00:00",
            "MessageAttributes": {
                "messageType": {"Type": "String", "Value": "RescueRequestEvaluatedEvent"},
                "correlationId": {"Type": "String", "Value": "corr-1"},
                "version": {"Type": "String", "Value": "1"},
            },
            "Message": json.dumps({
                "header": {
                    "messageType": "RescueRequestEvaluatedEvent",
                    "correlationId": "corr-1",
                    "sentAt": "2026-04-18T00:05:00+00:00",
                    "version": "1",
                },
                "body": {"requestId": "req-1"},
            }),
        }),
        "messageAttributes": {},
    }

    parsed = parse_prioritization_record(record)

    assert parsed["header"]["messageId"] == "sns-message-1"
    assert parsed["header"]["channel"] == "rescue.prioritization.created.v1"
    assert parsed["header"]["topicArn"].endswith("rescue-prioritization-created-v1-dev")
    assert parsed["body"]["requestId"] == "req-1"


def test_parses_sns_wrapped_updated_topic_and_infers_legacy_channel():
    record = {
        "messageId": "sqs-record-2",
        "body": json.dumps({
            "Type": "Notification",
            "MessageId": "sns-message-2",
            "TopicArn": "arn:aws:sns:ap-southeast-1:123456789012:rescue-prioritization-updated-v1-dev",
            "Timestamp": "2026-04-18T00:05:00+00:00",
            "MessageAttributes": {
                "messageType": {"Type": "String", "Value": "RescueRequestReEvaluateEvent"},
                "correlationId": {"Type": "String", "Value": "corr-2"},
                "version": {"Type": "String", "Value": "1"},
            },
            "Message": json.dumps({
                "header": {
                    "messageType": "RescueRequestReEvaluateEvent",
                    "correlationId": "corr-2",
                    "sentAt": "2026-04-18T00:05:00+00:00",
                    "version": "1",
                },
                "body": {"requestId": "req-2"},
            }),
        }),
        "messageAttributes": {},
    }

    parsed = parse_prioritization_record(record)

    assert parsed["header"]["channel"] == "rescue.prioritization.updated.v1"
    assert parsed["header"]["messageType"] == "RescueRequestReEvaluateEvent"
    assert parsed["body"]["requestId"] == "req-2"
