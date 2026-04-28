import json

import pytest

from src.adapters.auth import internal_api_key
from src.application.usecases import internal_maintenance
from src.handlers.internal import maintenance


def test_requires_matching_internal_api_key_from_env_config(monkeypatch):
    monkeypatch.setattr(internal_api_key, "INTERNAL_API_KEY", "secret-123")
    internal_api_key._load_internal_api_key.cache_clear()

    internal_api_key.require_internal_api_key("secret-123")


def test_rejects_wrong_internal_api_key_from_env_config(monkeypatch):
    monkeypatch.setattr(internal_api_key, "INTERNAL_API_KEY", "secret-123")
    internal_api_key._load_internal_api_key.cache_clear()

    with pytest.raises(Exception) as exc_info:
        internal_api_key.require_internal_api_key("wrong")

    assert exc_info.value.__class__.__name__ == "UnauthorizedError"


def test_clear_incident_catalog_without_requests(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        internal_maintenance,
        "delete_all_incidents",
        lambda: calls.append("incidents") or 3,
    )
    monkeypatch.setattr(
        internal_maintenance,
        "delete_all_request_items",
        lambda: calls.append("requests") or 10,
    )

    result = internal_maintenance.clear_incident_catalog(delete_requests=False)

    assert calls == ["incidents"]
    assert result == {
        "operation": "clear_incident_catalog",
        "deletedIncidents": 3,
        "deletedRequestItems": 0,
    }


def test_clear_incident_catalog_with_requests(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        internal_maintenance,
        "delete_all_request_items",
        lambda: calls.append("requests") or 10,
    )
    monkeypatch.setattr(
        internal_maintenance,
        "delete_all_incidents",
        lambda: calls.append("incidents") or 3,
    )

    result = internal_maintenance.clear_incident_catalog(delete_requests=True)

    assert calls == ["requests", "incidents"]
    assert result["deletedRequestItems"] == 10
    assert result["deletedIncidents"] == 3


def test_delete_orphaned_requests(monkeypatch):
    deleted_request_ids: set[str] = set()

    monkeypatch.setattr(
        internal_maintenance,
        "list_all_incidents",
        lambda: [{"incidentId": "inc-1"}],
    )
    monkeypatch.setattr(
        internal_maintenance,
        "list_request_master_refs",
        lambda: [
            {"requestId": "req-1", "incidentId": "inc-1"},
            {"requestId": "req-2", "incidentId": "missing"},
            {"requestId": "req-3", "incidentId": None},
        ],
    )

    def _delete_requests_by_ids(request_ids: set[str]) -> int:
        deleted_request_ids.update(request_ids)
        return 8

    monkeypatch.setattr(internal_maintenance, "delete_requests_by_ids", _delete_requests_by_ids)

    result = internal_maintenance.delete_orphaned_requests()

    assert deleted_request_ids == {"req-2", "req-3"}
    assert result["deletedRequests"] == 2
    assert result["deletedRequestItems"] == 8


def test_maintenance_handler_requires_api_key(monkeypatch):
    monkeypatch.setattr(maintenance, "require_internal_api_key", lambda api_key: None)
    monkeypatch.setattr(
        maintenance.internal_maintenance,
        "clear_requests",
        lambda: {"operation": "clear_requests", "deletedRequestItems": 5},
    )

    response = maintenance.handler(
        {
            "httpMethod": "DELETE",
            "resource": "/v1/internal/rescue-requests",
            "headers": {"api-key": "secret"},
        },
        None,
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["deletedRequestItems"] == 5
