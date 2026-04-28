import json

from src.handlers.internal import ingest_mission_status_changed as handler_module


def _record(message_id: str, body: dict) -> dict:
    return {
        "messageId": message_id,
        "body": json.dumps(body),
        "messageAttributes": {
            "messageType": {"StringValue": "MissionStatusChanged"},
        },
    }


def test_handler_reports_only_failed_mission_status_records(monkeypatch):
    processed: list[str] = []

    def _execute(message):
        body = message["body"]
        if body["requestId"] == "bad-req":
            raise RuntimeError("boom")
        processed.append(body["requestId"])
        return {"status": "updated", "requestId": body["requestId"]}

    monkeypatch.setattr(handler_module.ingest_mission_status_changed, "execute", _execute)

    event = {
        "Records": [
            _record(
                "message-good",
                {
                    "schema_version": "1.0",
                    "mission_id": "mission-1",
                    "requestId": "req-1",
                    "incident_id": "incident-1",
                    "rescue_team_id": "team-1",
                    "new_status": "EN_ROUTE",
                    "changed_at": "2026-04-29T00:04:00+00:00",
                    "changed_by": "team-1",
                },
            ),
            _record(
                "message-bad",
                {
                    "schema_version": "1.0",
                    "mission_id": "mission-2",
                    "requestId": "bad-req",
                    "incident_id": "incident-1",
                    "rescue_team_id": "team-1",
                    "new_status": "EN_ROUTE",
                    "changed_at": "2026-04-29T00:05:00+00:00",
                    "changed_by": "team-1",
                },
            ),
        ]
    }

    result = handler_module.handler(event, None)

    assert processed == ["req-1"]
    assert result == {"batchItemFailures": [{"itemIdentifier": "message-bad"}]}
