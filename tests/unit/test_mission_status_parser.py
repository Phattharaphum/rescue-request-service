import json

from src.adapters.messaging.mission_status_parser import parse_mission_status_record


def test_parses_sns_wrapped_mission_status_topic():
    record = {
        "messageId": "sqs-record-1",
        "body": json.dumps(
            {
                "Type": "Notification",
                "MessageId": "sns-message-1",
                "TopicArn": "arn:aws:sns:ap-southeast-1:123456789012:mission-status-changed-v1-dev",
                "Timestamp": "2026-04-29T00:05:00+00:00",
                "MessageAttributes": {
                    "messageType": {"Type": "String", "Value": "MissionStatusChanged"},
                    "correlationId": {"Type": "String", "Value": "mission-corr-1"},
                    "schemaVersion": {"Type": "String", "Value": "1.0"},
                },
                "Message": json.dumps(
                    {
                        "schema_version": "1.0",
                        "mission_id": "mission-1",
                        "requestId": "req-1",
                        "incident_id": "incident-1",
                        "rescue_team_id": "team-1",
                        "old_status": "ASSIGNED",
                        "new_status": "EN_ROUTE",
                        "changed_at": "2026-04-29T00:04:00+00:00",
                        "changed_by": "team-1",
                    }
                ),
            }
        ),
        "messageAttributes": {},
    }

    parsed = parse_mission_status_record(record)

    assert parsed["header"]["messageId"] == "sns-message-1"
    assert parsed["header"]["messageType"] == "MissionStatusChanged"
    assert parsed["header"]["channel"] == "mission.status.changed.v1"
    assert parsed["body"]["requestId"] == "req-1"
    assert parsed["body"]["new_status"] == "EN_ROUTE"


def test_parses_direct_sqs_payload():
    payload = {
        "schema_version": "1.0",
        "mission_id": "mission-2",
        "requestId": "req-2",
        "incident_id": "incident-2",
        "rescue_team_id": "team-2",
        "new_status": "RESOLVED",
        "changed_at": "2026-04-29T00:05:00Z",
        "changed_by": "team-2",
    }
    record = {
        "messageId": "sqs-record-2",
        "body": json.dumps(payload),
        "messageAttributes": {
            "messageType": {"StringValue": "MissionStatusChanged"},
        },
    }

    parsed = parse_mission_status_record(record)

    assert parsed["header"]["messageId"] == "sqs-record-2"
    assert parsed["header"]["messageType"] == "MissionStatusChanged"
    assert parsed["body"] == payload
