import json

import pytest

from src.application.usecases import ingest_rescue_request_evaluation as usecase
from src.shared.errors import NotFoundError, ValidationError


def _message(priority_score=0.3, correlation_id="msg-1") -> dict:
    return {
        "header": {
            "messageType": "RescueRequestEvaluatedEvent",
            "messageId": "sns-msg-1",
            "correlationId": correlation_id,
            "sentAt": "2026-04-17T00:05:00+00:00",
            "version": "1",
        },
        "body": {
            "requestId": "req-1",
            "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
            "evaluateId": "812748a6-5a3a-43c5-8b4f-140034ece737",
            "requestType": "FLOOD",
            "priorityScore": priority_score,
            "priorityLevel": "NORMAL",
            "evaluateReason": "Needs assistance but not life threatening.",
            "lastEvaluatedAt": "2026-04-17T00:04:30+00:00",
            "description": "No food reserves",
            "location": {
                "latitude": 13.75,
                "longitude": 100.5,
            },
            "peopleCount": 1,
        },
    }


def test_updates_current_state_and_finalizes_success(monkeypatch):
    updated_calls: dict = {}
    finalized: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(
        usecase,
        "get_current_state",
        lambda request_id: {
            "requestId": request_id,
            "status": "TRIAGED",
            "lastPrioritizationMessageId": "msg-1",
        },
    )
    monkeypatch.setattr(
        usecase,
        "update_current_fields",
        lambda request_id, updates, expected_version=None: updated_calls.update({
            "request_id": request_id,
            "updates": updates,
        }),
    )
    monkeypatch.setattr(
        usecase,
        "finalize_success",
        lambda **kwargs: finalized.update(kwargs),
    )
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not fail")))

    result = usecase.execute(_message())

    assert result["status"] == "updated"
    assert updated_calls["request_id"] == "req-1"
    assert updated_calls["updates"]["priorityScore"] == 0.3
    assert updated_calls["updates"]["priorityLevel"] == "NORMAL"
    assert updated_calls["updates"]["latestPriorityEvaluationId"] == "812748a6-5a3a-43c5-8b4f-140034ece737"
    assert updated_calls["updates"]["latestPriorityCorrelationId"] == "msg-1"
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


def test_rejects_invalid_priority_score(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)

    with pytest.raises(ValidationError):
        usecase.execute(_message(priority_score=1.5))
