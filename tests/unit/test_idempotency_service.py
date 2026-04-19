import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("STAGE", "local")
os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:4566")
os.environ.setdefault("AWS_REGION", "ap-southeast-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from src.application.services import idempotency_service as service


def test_check_and_reserve_uses_scoped_key(monkeypatch):
    saved_record: dict = {}
    body = {"description": "help me", "peopleCount": 2}

    monkeypatch.setattr(service, "get_idempotency_record", lambda key_hash: None)
    monkeypatch.setattr(
        service,
        "reserve_idempotency_key",
        lambda record: saved_record.update(record) or True,
    )

    reservation = service.check_and_reserve(
        idempotency_key="same-key",
        operation_name="PatchRescueRequest",
        resource_scope="PATCH:/v1/rescue-requests/req-1",
        request_body=body,
    )

    assert reservation["replay"] is False
    assert saved_record["operationName"] == "PatchRescueRequest"
    assert saved_record["resourceScope"] == "PATCH:/v1/rescue-requests/req-1"
    assert saved_record["idempotencyKeyHash"] == reservation["keyHash"]


def test_check_and_reserve_reclaims_expired_in_progress_lock(monkeypatch):
    body = {"description": "help me", "peopleCount": 2}
    fingerprint = service.compute_request_fingerprint(body)
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    captured: dict = {}

    monkeypatch.setattr(
        service,
        "get_idempotency_record",
        lambda key_hash: {
            "status": "IN_PROGRESS",
            "requestFingerprint": fingerprint,
            "operationName": "PatchRescueRequest",
            "resourceScope": "PATCH:/v1/rescue-requests/req-1",
            "lockExpiresAt": expired,
        },
    )
    monkeypatch.setattr(
        service,
        "reclaim_expired_in_progress_idempotency_key",
        lambda **kwargs: captured.update(kwargs) or True,
    )
    monkeypatch.setattr(
        service,
        "retry_failed_idempotency_key",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("retry_failed should not be called")),
    )

    reservation = service.check_and_reserve(
        idempotency_key="same-key",
        operation_name="PatchRescueRequest",
        resource_scope="PATCH:/v1/rescue-requests/req-1",
        request_body=body,
    )

    assert reservation["replay"] is False
    assert reservation["lockOwner"]
    assert captured["expected_lock_expires_at"] == expired
    assert captured["operation_name"] == "PatchRescueRequest"
    assert captured["resource_scope"] == "PATCH:/v1/rescue-requests/req-1"


def test_check_and_reserve_retries_failed_key_safely(monkeypatch):
    body = {"description": "help me", "peopleCount": 2}
    fingerprint = service.compute_request_fingerprint(body)
    captured: dict = {}

    monkeypatch.setattr(
        service,
        "get_idempotency_record",
        lambda key_hash: {
            "status": "FAILED",
            "requestFingerprint": fingerprint,
            "operationName": "PatchRescueRequest",
            "resourceScope": "PATCH:/v1/rescue-requests/req-1",
        },
    )
    monkeypatch.setattr(
        service,
        "retry_failed_idempotency_key",
        lambda **kwargs: captured.update(kwargs) or True,
    )
    monkeypatch.setattr(
        service,
        "reclaim_expired_in_progress_idempotency_key",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("reclaim should not be called")),
    )

    reservation = service.check_and_reserve(
        idempotency_key="same-key",
        operation_name="PatchRescueRequest",
        resource_scope="PATCH:/v1/rescue-requests/req-1",
        request_body=body,
    )

    assert reservation["replay"] is False
    assert reservation["lockOwner"]
    assert captured["operation_name"] == "PatchRescueRequest"
    assert captured["resource_scope"] == "PATCH:/v1/rescue-requests/req-1"


def test_check_and_reserve_handles_failed_race_and_replays_completed(monkeypatch):
    body = {"description": "help me", "peopleCount": 2}
    fingerprint = service.compute_request_fingerprint(body)
    records = [
        {
            "status": "FAILED",
            "requestFingerprint": fingerprint,
            "operationName": "PatchRescueRequest",
            "resourceScope": "PATCH:/v1/rescue-requests/req-1",
        },
        {
            "status": "COMPLETED",
            "requestFingerprint": fingerprint,
            "responseStatusCode": 200,
            "responseBody": '{"ok":true}',
            "resultResourceId": "req-1",
        },
    ]

    def fake_get(_: str):
        if records:
            return records.pop(0)
        return {
            "status": "COMPLETED",
            "requestFingerprint": fingerprint,
            "responseStatusCode": 200,
            "responseBody": '{"ok":true}',
            "resultResourceId": "req-1",
        }

    monkeypatch.setattr(service, "get_idempotency_record", fake_get)
    monkeypatch.setattr(service, "retry_failed_idempotency_key", lambda **kwargs: False)

    reservation = service.check_and_reserve(
        idempotency_key="same-key",
        operation_name="PatchRescueRequest",
        resource_scope="PATCH:/v1/rescue-requests/req-1",
        request_body=body,
    )

    assert reservation["replay"] is True
    assert reservation["statusCode"] == 200
    assert reservation["body"] == '{"ok":true}'
