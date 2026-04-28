import json

import pytest

from src.adapters.external import incident_tracking_client
from src.shared.errors import ServiceUnavailableError


class _FakeResponse:
    status = 200

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self):
        return self.status


def test_fetch_incidents_uses_environment_config(monkeypatch):
    captured = {}

    def _fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return _FakeResponse([{"incident_id": "inc-1"}])

    monkeypatch.setattr(
        incident_tracking_client,
        "INCIDENT_SYNC_API_URL",
        "https://incident.example.test/api/v1/incidents",
    )
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_API_KEY", "test-key")
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_ACCEPT", "application/json")
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_TRANSACTION_ID_HEADER", "X-Test-Txn")
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS", 9)
    monkeypatch.setattr(incident_tracking_client, "urlopen", _fake_urlopen)
    incident_tracking_client._load_incident_tracking_config.cache_clear()

    result = incident_tracking_client.fetch_incidents()

    assert result == [{"incident_id": "inc-1"}]
    assert captured["url"] == "https://incident.example.test/api/v1/incidents"
    assert captured["headers"]["Api-key"] == "test-key"
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["headers"]["X-test-txn"]
    assert captured["timeout"] == 9


def test_fetch_incidents_requires_api_url(monkeypatch):
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_API_URL", "")
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_API_KEY", "test-key")
    incident_tracking_client._load_incident_tracking_config.cache_clear()

    with pytest.raises(ServiceUnavailableError):
        incident_tracking_client.fetch_incidents()


def test_fetch_incidents_requires_api_key(monkeypatch):
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_API_URL", "https://incident.example.test")
    monkeypatch.setattr(incident_tracking_client, "INCIDENT_SYNC_API_KEY", "")
    incident_tracking_client._load_incident_tracking_config.cache_clear()

    with pytest.raises(ServiceUnavailableError):
        incident_tracking_client.fetch_incidents()
