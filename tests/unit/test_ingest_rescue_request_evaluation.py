import json

import pytest

from src.application.usecases import ingest_rescue_request_evaluation as usecase
from src.shared.errors import NotFoundError, ValidationError


def _message(
    *,
    priority_score: float = 0.3,
    correlation_id: str = "msg-1",
    message_type: str = "RescueRequestEvaluatedEvent",
    channel: str | None = None,
) -> dict:
    return {
        "header": {
            "messageType": message_type,
            "messageId": "6f9f3179-317a-42a6-9b0c-5a799a0c8bd9",
            "correlationId": correlation_id,
            "sentAt": "2026-04-17T00:05:00+00:00",
            "version": "1",
            "channel": channel,
        },
        "body": {
            "requestId": "req-1",
            "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
            "evaluateId": "812748a6-5a3a-43c5-8b4f-140034ece737",
            "requestType": "FLOOD",
            "priorityScore": priority_score,
            "priorityLevel": "NORMAL",
            "evaluateReason": "Needs assistance but not life threatening.",
            "submittedAt": "2026-04-17T00:00:00+00:00",
            "lastEvaluatedAt": "2026-04-17T00:04:30+00:00",
            "description": "No food reserves",
            "location": {
                "latitude": 13.75,
                "longitude": 100.5,
            },
            "peopleCount": 1,
            "specialNeeds": ["children"],
        },
    }


def _current_state(request_id: str, status: str = "SUBMITTED", correlation_id: str = "msg-1") -> dict:
    return {
        "requestId": request_id,
        "status": status,
        "latestPrioritySourceEventId": correlation_id,
        "stateVersion": 1,
    }


def test_appends_event_updates_current_state_publishes_and_finalizes_success(monkeypatch):
    appended_calls: dict = {}
    published_calls: dict = {}
    finalized: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state(request_id))
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda request_id, event_item, current_updates, expected_version=None: appended_calls.update({
            "request_id": request_id,
            "event_item": event_item,
            "updates": current_updates,
            "expected_version": expected_version,
        }),
    )
    monkeypatch.setattr(
        usecase,
        "publish_status_changed",
        lambda request_id, previous_status, new_status, event_id, version, correlation_id=None: published_calls.update({
            "request_id": request_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "event_id": event_id,
            "version": version,
            "correlation_id": correlation_id,
        }),
    )
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: finalized.update(kwargs))
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not fail")))

    result = usecase.execute(_message())

    assert result["status"] == "updated"
    assert appended_calls["request_id"] == "req-1"
    assert appended_calls["updates"]["priorityScore"] == 0.3
    assert appended_calls["updates"]["priorityLevel"] == "NORMAL"
    assert appended_calls["updates"]["status"] == "TRIAGED"
    assert appended_calls["updates"]["latestPriorityEvaluationId"] == "812748a6-5a3a-43c5-8b4f-140034ece737"
    assert appended_calls["updates"]["latestPriorityCorrelationId"] == "msg-1"
    assert appended_calls["updates"]["stateVersion"] == 2
    assert appended_calls["event_item"]["itemType"] == "STATUS_EVENT"
    assert appended_calls["event_item"]["previousStatus"] == "SUBMITTED"
    assert appended_calls["event_item"]["newStatus"] == "TRIAGED"
    assert appended_calls["expected_version"] == 1
    assert published_calls["request_id"] == "req-1"
    assert published_calls["previous_status"] == "SUBMITTED"
    assert published_calls["new_status"] == "TRIAGED"
    assert published_calls["event_id"] == appended_calls["event_item"]["eventId"]
    assert published_calls["version"] == 2
    assert published_calls["correlation_id"] == "msg-1"
    assert finalized["result_resource_id"] == "req-1"
    assert json.loads(finalized["response_body"])["status"] == "updated"


def test_returns_duplicate_when_idempotency_replays(monkeypatch):
    monkeypatch.setattr(
        usecase,
        "check_and_reserve",
        lambda **kwargs: {"replay": True, "body": "{}", "statusCode": 200},
    )

    result = usecase.execute(_message())

    assert result == {
        "status": "duplicate",
        "requestId": "req-1",
        "evaluateId": "812748a6-5a3a-43c5-8b4f-140034ece737",
    }


def test_raises_when_request_is_missing(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    with pytest.raises(NotFoundError):
        usecase.execute(_message())


@pytest.mark.parametrize(
    ("field", "mutator"),
    [
        ("body.priorityScore", lambda payload: payload["body"].__setitem__("priorityScore", 1.01)),
        ("body.incidentId", lambda payload: payload["body"].__setitem__("incidentId", "not-a-uuid")),
        ("body.evaluateId", lambda payload: payload["body"].__setitem__("evaluateId", "eval-001")),
        ("body.priorityLevel", lambda payload: payload["body"].__setitem__("priorityLevel", "URGENT")),
        ("body.location", lambda payload: payload["body"].pop("location")),
    ],
)
def test_rejects_invalid_evaluated_event_payload(field, mutator):
    message = _message()
    mutator(message)

    with pytest.raises(ValidationError) as exc_info:
        usecase.execute(message)

    assert any(detail["field"] == field for detail in exc_info.value.details)


def test_accepts_missing_submitted_at(monkeypatch):
    appended_calls: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state(request_id))
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda request_id, event_item, current_updates, expected_version=None: appended_calls.update({
            "request_id": request_id,
            "updates": current_updates,
        }),
    )
    monkeypatch.setattr(usecase, "publish_status_changed", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    message = _message()
    message["body"].pop("submittedAt", None)

    result = usecase.execute(message)

    assert result["status"] == "updated"
    assert appended_calls["request_id"] == "req-1"
    assert appended_calls["updates"]["priorityScore"] == 0.3
    assert appended_calls["updates"]["priorityLevel"] == "NORMAL"


def test_accepts_prioritization_service_message_shape(monkeypatch):
    appended_calls: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(
        usecase,
        "get_current_state",
        lambda request_id: _current_state(
            request_id,
            correlation_id="3df04bc4-1de3-49d0-a47c-b9e76d2bd36c",
        ),
    )
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda request_id, event_item, current_updates, expected_version=None: appended_calls.update({
            "request_id": request_id,
            "updates": current_updates,
        }),
    )
    monkeypatch.setattr(usecase, "publish_status_changed", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    result = usecase.execute({
        "header": {
            "messageId": "4a5f9766-6c17-4c10-8cc3-87bcdf5f6572",
            "eventType": "rescue.prioritization.evaluated.v1",
            "schemaVersion": "1.0",
            "producer": "rescue-prioritization-service",
            "occurredAt": "2026-04-17T10:00:00Z",
            "traceId": "trace-123",
            "correlationId": "3df04bc4-1de3-49d0-a47c-b9e76d2bd36c",
            "partitionKey": "79b7a158-4230-453a-8d18-d03d96f87b6a",
            "contentType": "application/json",
        },
        "body": {
            "requestId": "79b7a158-4230-453a-8d18-d03d96f87b6a",
            "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
            "requestType": "FLOOD",
            "priorityScore": 0.925,
            "priorityLevel": "CRITICAL",
            "evaluationId": "812748a6-5a3a-43c5-8b4f-140034ece737",
            "reason": "Children and bedridden residents need urgent rescue.",
            "evaluatedAt": "2026-04-17T10:00:00Z",
            "submittedAt": "2026-04-17T09:45:00Z",
            "description": "Need urgent evacuation",
            "location": {
                "latitude": 13.7563,
                "longitude": 100.5018,
            },
            "peopleCount": 2,
            "specialNeeds": ["bedridden", "children"],
        },
    })

    assert result["status"] == "updated"
    assert appended_calls["request_id"] == "79b7a158-4230-453a-8d18-d03d96f87b6a"
    assert appended_calls["updates"]["priorityScore"] == 0.925
    assert appended_calls["updates"]["priorityLevel"] == "CRITICAL"
    assert appended_calls["updates"]["status"] == "TRIAGED"
    assert appended_calls["updates"]["latestPriorityEvaluationId"] == "812748a6-5a3a-43c5-8b4f-140034ece737"


def test_accepts_legacy_re_evaluate_message_type_on_updated_channel(monkeypatch):
    appended_calls: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state(request_id))
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda request_id, event_item, current_updates, expected_version=None: appended_calls.update({
            "request_id": request_id,
            "updates": current_updates,
        }),
    )
    monkeypatch.setattr(usecase, "publish_status_changed", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    result = usecase.execute(
        _message(
            message_type="RescueRequestReEvaluateEvent",
            channel="rescue.prioritization.updated.v1",
        )
    )

    assert result["status"] == "updated"
    assert appended_calls["updates"]["latestPriorityEvaluationId"] == "812748a6-5a3a-43c5-8b4f-140034ece737"


def test_rejects_legacy_re_evaluate_message_type_on_created_channel():
    with pytest.raises(ValidationError) as exc_info:
        usecase.execute(
            _message(
                message_type="RescueRequestReEvaluateEvent",
                channel="rescue.prioritization.created.v1",
            )
        )

    assert any(detail["field"] == "header.messageType" for detail in exc_info.value.details)


def test_rejects_stale_correlation_id(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(
        usecase,
        "get_current_state",
        lambda request_id: _current_state(request_id, correlation_id="msg-latest"),
    )
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    with pytest.raises(ValidationError) as exc_info:
        usecase.execute(_message(correlation_id="msg-old"))

    assert any(detail["field"] == "header.correlationId" for detail in exc_info.value.details)
