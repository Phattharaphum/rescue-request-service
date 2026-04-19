from src.application.usecases import create_citizen_update
from src.application.usecases import create_rescue_request
from src.application.usecases import patch_rescue_request


def test_create_request_stores_latest_priority_source_event_metadata(monkeypatch):
    captured_updates: dict = {}

    monkeypatch.setattr(create_rescue_request, "find_by_phone_hash", lambda _phone_hash: None)
    monkeypatch.setattr(create_rescue_request, "detect_duplicate", lambda **kwargs: None)
    monkeypatch.setattr(create_rescue_request, "normalize_phone", lambda phone: phone)
    monkeypatch.setattr(create_rescue_request, "hash_phone", lambda phone: f"hash::{phone}")
    monkeypatch.setattr(create_rescue_request, "generate_tracking_code", lambda: "123456")
    monkeypatch.setattr(create_rescue_request, "hash_tracking_code", lambda value: f"track::{value}")
    monkeypatch.setattr(create_rescue_request, "get_duplicate_signature", lambda **kwargs: "dup-signature")
    monkeypatch.setattr(create_rescue_request, "create_rescue_request", lambda **kwargs: None)
    monkeypatch.setattr(
        create_rescue_request,
        "publish_request_created",
        lambda **kwargs: {
            "messageId": "1f8b9d06-6c3a-4d34-a095-6f34d61d3a81",
            "eventType": "rescue-request.created",
            "occurredAt": "2026-04-18T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        create_rescue_request,
        "update_current_fields",
        lambda request_id, updates: captured_updates.update({"request_id": request_id, "updates": updates}),
    )

    result = create_rescue_request.execute({
        "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
        "requestType": "FLOOD",
        "description": "Need evacuation",
        "peopleCount": 2,
        "latitude": 13.75,
        "longitude": 100.5,
        "contactName": "Test User",
        "contactPhone": "0812345678",
        "sourceChannel": "WEB",
    })

    assert result["requestId"] == captured_updates["request_id"]
    assert captured_updates["updates"] == {
        "latestPrioritySourceEventId": "1f8b9d06-6c3a-4d34-a095-6f34d61d3a81",
        "latestPrioritySourceEventType": "rescue-request.created",
        "latestPrioritySourceOccurredAt": "2026-04-18T00:00:00+00:00",
    }


def test_create_citizen_update_stores_latest_priority_source_event_metadata(monkeypatch):
    captured_updates: dict = {}

    monkeypatch.setattr(
        create_citizen_update,
        "get_current_state",
        lambda request_id: {"requestId": request_id, "status": "SUBMITTED"},
    )
    monkeypatch.setattr(
        create_citizen_update,
        "get_master",
        lambda request_id: {"requestId": request_id, "trackingCodeHash": "track::123456"},
    )
    monkeypatch.setattr(create_citizen_update, "hash_tracking_code", lambda value: f"track::{value}")
    monkeypatch.setattr(create_citizen_update, "put_citizen_update", lambda item: None)
    monkeypatch.setattr(create_citizen_update, "update_master_fields", lambda request_id, updates: None)
    monkeypatch.setattr(
        create_citizen_update,
        "publish_citizen_updated",
        lambda **kwargs: {
            "messageId": "58e0e0ec-cab0-4890-8d54-f9dca112df5e",
            "eventType": "rescue-request.citizen-updated",
            "occurredAt": "2026-04-18T01:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        create_citizen_update,
        "update_current_fields",
        lambda request_id, updates: captured_updates.update({"request_id": request_id, "updates": updates}),
    )

    result = create_citizen_update.execute(
        request_id="req-1",
        body={
            "trackingCode": "123456",
            "updateType": "NOTE",
            "updatePayload": {"note": "Water is rising"},
        },
    )

    assert result["requestId"] == "req-1"
    assert captured_updates["updates"] == {
        "latestPrioritySourceEventId": "58e0e0ec-cab0-4890-8d54-f9dca112df5e",
        "latestPrioritySourceEventType": "rescue-request.citizen-updated",
        "latestPrioritySourceOccurredAt": "2026-04-18T01:00:00+00:00",
    }


def test_patch_request_stores_latest_priority_source_event_metadata(monkeypatch):
    captured_updates: dict = {}

    monkeypatch.setattr(
        patch_rescue_request,
        "get_current_state",
        lambda request_id: {"requestId": request_id, "status": "SUBMITTED"},
    )
    monkeypatch.setattr(
        patch_rescue_request,
        "get_master",
        lambda request_id: {"requestId": request_id, "description": "Old description"},
    )
    monkeypatch.setattr(patch_rescue_request, "update_master_fields", lambda request_id, updates, expected_version=None: None)
    monkeypatch.setattr(
        patch_rescue_request,
        "publish_citizen_updated",
        lambda **kwargs: {
            "messageId": "d1e60ee4-c3e6-4240-a9f4-b4d0bf28ccf9",
            "eventType": "rescue-request.citizen-updated",
            "occurredAt": "2026-04-18T02:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        patch_rescue_request,
        "update_current_fields",
        lambda request_id, updates: captured_updates.update({"request_id": request_id, "updates": updates}),
    )

    result = patch_rescue_request.execute(
        request_id="req-2",
        body={"description": "Updated description"},
    )

    assert result["requestId"] == "req-2"
    assert captured_updates["updates"] == {
        "latestPrioritySourceEventId": "d1e60ee4-c3e6-4240-a9f4-b4d0bf28ccf9",
        "latestPrioritySourceEventType": "rescue-request.citizen-updated",
        "latestPrioritySourceOccurredAt": "2026-04-18T02:00:00+00:00",
    }
