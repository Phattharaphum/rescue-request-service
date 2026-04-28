import json

import pytest

from src.application.usecases import ingest_mission_status_changed as usecase
from src.shared.errors import NotFoundError, ValidationError


def _message(new_status: str = "EN_ROUTE", *, request_id: str = "req-1", incident_id: str = "incident-1") -> dict:
    return {
        "header": {
            "messageId": "sns-message-1",
            "messageType": "MissionStatusChanged",
            "correlationId": "mission-corr-1",
            "sentAt": "2026-04-29T00:05:00+00:00",
            "version": "1",
            "channel": "mission.status.changed.v1",
        },
        "body": {
            "schema_version": "1.0",
            "mission_id": "mission-1",
            "requestId": request_id,
            "incident_id": incident_id,
            "rescue_team_id": "team-1",
            "old_status": "ASSIGNED",
            "new_status": new_status,
            "changed_at": "2026-04-29T00:04:00+00:00",
            "changed_by": "team-1",
        },
    }


def _current_state(status: str = "ASSIGNED") -> dict:
    return {
        "requestId": "req-1",
        "incidentId": "incident-1",
        "status": status,
        "stateVersion": 3,
        "priorityScore": 0.7,
    }


def test_en_route_updates_request_to_in_progress_and_stores_mission_metadata(monkeypatch):
    appended_calls: dict = {}
    published_calls: dict = {}
    finalized: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state())
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda request_id, event_item, current_updates, expected_version=None: appended_calls.update(
            {
                "request_id": request_id,
                "event_item": event_item,
                "updates": current_updates,
                "expected_version": expected_version,
            }
        ),
    )
    monkeypatch.setattr(
        usecase,
        "publish_status_changed",
        lambda request_id, previous_status, new_status, event_id, version, correlation_id=None: published_calls.update(
            {
                "request_id": request_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "event_id": event_id,
                "version": version,
                "correlation_id": correlation_id,
            }
        ),
    )
    monkeypatch.setattr(usecase, "publish_resolved", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unused")))
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: finalized.update(kwargs))
    monkeypatch.setattr(
        usecase, "finalize_failure", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not fail"))
    )

    result = usecase.execute(_message())

    assert result["status"] == "updated"
    assert result["previousStatus"] == "ASSIGNED"
    assert result["newStatus"] == "IN_PROGRESS"
    assert appended_calls["request_id"] == "req-1"
    assert appended_calls["expected_version"] == 3
    assert appended_calls["updates"]["status"] == "IN_PROGRESS"
    assert appended_calls["updates"]["latestMissionId"] == "mission-1"
    assert appended_calls["updates"]["latestMissionRescueTeamId"] == "team-1"
    assert appended_calls["updates"]["latestMissionChangedBy"] == "team-1"
    assert appended_calls["updates"]["latestMissionStatus"] == "EN_ROUTE"
    assert appended_calls["updates"]["assignedUnitId"] == "team-1"
    assert appended_calls["event_item"]["previousStatus"] == "ASSIGNED"
    assert appended_calls["event_item"]["newStatus"] == "IN_PROGRESS"
    assert appended_calls["event_item"]["changedBy"] == "team-1"
    assert appended_calls["event_item"]["changedByRole"] == "mission-progress-service"
    assert appended_calls["event_item"]["missionId"] == "mission-1"
    assert appended_calls["event_item"]["rescueTeamId"] == "team-1"
    assert appended_calls["event_item"]["meta"]["missionStatus"] == "EN_ROUTE"
    assert published_calls["new_status"] == "IN_PROGRESS"
    assert published_calls["correlation_id"] == "mission-corr-1"
    assert finalized["result_resource_id"] == "req-1"
    assert json.loads(finalized["response_body"])["status"] == "updated"


def test_resolved_updates_status_and_publishes_resolved_event(monkeypatch):
    resolved_calls: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state(status="IN_PROGRESS"))
    monkeypatch.setattr(usecase, "append_event_and_update_current", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "publish_status_changed", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "publish_resolved", lambda **kwargs: resolved_calls.update(kwargs))
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    result = usecase.execute(_message("RESOLVED"))

    assert result["status"] == "updated"
    assert result["newStatus"] == "RESOLVED"
    assert resolved_calls["request_id"] == "req-1"
    assert resolved_calls["correlation_id"] == "mission-corr-1"


def test_unmapped_known_status_updates_metadata_without_status_event(monkeypatch):
    metadata_calls: dict = {}

    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state(status="IN_PROGRESS"))
    monkeypatch.setattr(
        usecase,
        "update_current_fields",
        lambda request_id, updates, expected_version=None: metadata_calls.update(
            {
                "request_id": request_id,
                "updates": updates,
                "expected_version": expected_version,
            }
        ),
    )
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not append status event")),
    )
    monkeypatch.setattr(
        usecase, "publish_status_changed", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unused"))
    )
    monkeypatch.setattr(usecase, "publish_resolved", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unused")))
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    result = usecase.execute(_message("ON_SITE"))

    assert result["status"] == "metadata_updated_unmapped_status"
    assert metadata_calls["request_id"] == "req-1"
    assert metadata_calls["expected_version"] == 3
    assert metadata_calls["updates"]["latestMissionStatus"] == "ON_SITE"
    assert "status" not in metadata_calls["updates"]


def test_returns_duplicate_when_idempotency_replays(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: {"replay": True})

    result = usecase.execute(_message())

    assert result == {
        "status": "duplicate",
        "requestId": "req-1",
        "missionId": "mission-1",
        "missionStatus": "EN_ROUTE",
    }


def test_skips_terminal_request(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state(status="RESOLVED"))
    monkeypatch.setattr(
        usecase,
        "append_event_and_update_current",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not append")),
    )
    monkeypatch.setattr(
        usecase, "update_current_fields", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unused"))
    )
    monkeypatch.setattr(usecase, "finalize_success", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    result = usecase.execute(_message("RESOLVED"))

    assert result["status"] == "skipped_terminal"
    assert result["currentStatus"] == "RESOLVED"


def test_raises_when_request_is_missing(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: None)
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    with pytest.raises(NotFoundError):
        usecase.execute(_message())


def test_rejects_unknown_mission_status():
    message = _message("DISPATCHED")

    with pytest.raises(ValidationError) as exc_info:
        usecase.execute(message)

    assert any(detail["field"] == "body.new_status" for detail in exc_info.value.details)


def test_rejects_incident_mismatch(monkeypatch):
    monkeypatch.setattr(usecase, "check_and_reserve", lambda **kwargs: None)
    monkeypatch.setattr(usecase, "get_current_state", lambda request_id: _current_state())
    monkeypatch.setattr(usecase, "finalize_failure", lambda **kwargs: None)

    with pytest.raises(ValidationError) as exc_info:
        usecase.execute(_message(incident_id="incident-other"))

    assert any(detail["field"] == "body.incident_id" for detail in exc_info.value.details)
