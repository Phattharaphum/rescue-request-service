import pytest
from botocore.exceptions import ClientError

from src.application.usecases import update_rescue_request_priority as usecase
from src.shared.errors import ConflictError, ValidationError


def _base_current_state(priority_score: float | int | None = 0.4) -> dict:
    return {
        "requestId": "req-1",
        "status": "TRIAGED",
        "stateVersion": 2,
        "priorityScore": priority_score,
        "priorityLevel": "MEDIUM",
        "latestNote": "Initial triage",
    }


def test_updates_priority_fields_and_publishes_priority_event(monkeypatch):
    updated_calls: dict = {}
    published_calls: dict = {}

    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _base_current_state())
    monkeypatch.setattr(
        usecase,
        "update_current_fields",
        lambda request_id, updates, expected_version=None: updated_calls.update({
            "request_id": request_id,
            "updates": updates,
            "expected_version": expected_version,
        }),
    )
    monkeypatch.setattr(
        usecase,
        "publish_priority_score_updated",
        lambda **kwargs: published_calls.update(kwargs),
    )

    result = usecase.execute(
        request_id="req-1",
        body={"priorityScore": 0.755, "priorityLevel": "HIGH", "note": "Escalated"},
        expected_version=2,
    )

    assert result["requestId"] == "req-1"
    assert result["priorityScore"] == 0.755
    assert result["priorityLevel"] == "HIGH"
    assert result["note"] == "Escalated"
    assert result["updated"] == ["priorityScore", "priorityLevel", "note"]

    assert updated_calls["request_id"] == "req-1"
    assert updated_calls["expected_version"] == 2
    assert updated_calls["updates"]["priorityScore"] == 0.755
    assert updated_calls["updates"]["priorityLevel"] == "HIGH"
    assert updated_calls["updates"]["latestNote"] == "Escalated"
    assert "lastUpdatedAt" in updated_calls["updates"]

    assert published_calls["request_id"] == "req-1"
    assert published_calls["previous_priority_score"] == 0.4
    assert published_calls["new_priority_score"] == 0.755
    assert published_calls["priority_level"] == "HIGH"
    assert published_calls["note"] == "Escalated"
    assert published_calls["correlation_id"] == "req-1"


def test_note_only_update_does_not_publish_priority_event(monkeypatch):
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _base_current_state())
    monkeypatch.setattr(usecase, "update_current_fields", lambda request_id, updates, expected_version=None: None)

    def _should_not_publish(**kwargs):
        raise AssertionError("priority score event should not be published for note-only update")

    monkeypatch.setattr(usecase, "publish_priority_score_updated", _should_not_publish)

    result = usecase.execute(
        request_id="req-1",
        body={"note": "Need urgent response"},
    )

    assert result["updated"] == ["note"]
    assert result["note"] == "Need urgent response"


def test_rejects_terminal_request(monkeypatch):
    state = _base_current_state()
    state["status"] = "RESOLVED"
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: state)

    with pytest.raises(ConflictError):
        usecase.execute(request_id="req-1", body={"priorityScore": 0.99})


def test_requires_valid_priority_score(monkeypatch):
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _base_current_state())

    with pytest.raises(ValidationError):
        usecase.execute(request_id="req-1", body={"priorityScore": "high"})


def test_rejects_out_of_range_priority_score(monkeypatch):
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _base_current_state())

    with pytest.raises(ValidationError):
        usecase.execute(request_id="req-1", body={"priorityScore": 1.01})


def test_conditional_check_failure_returns_conflict(monkeypatch):
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _base_current_state())

    def _raise_conditional(*args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "conditional check failed"}},
            "UpdateItem",
        )

    monkeypatch.setattr(usecase, "update_current_fields", _raise_conditional)

    with pytest.raises(ConflictError):
        usecase.execute(request_id="req-1", body={"priorityScore": 0.77}, expected_version=2)
