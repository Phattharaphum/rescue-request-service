from src.application.services import incident_catalog_seed


def test_ensure_mock_incidents_seeded_inserts_all_missing_items(monkeypatch):
    upserted: list[dict] = []

    monkeypatch.setattr(incident_catalog_seed, "list_all_incidents", lambda: [])
    monkeypatch.setattr(incident_catalog_seed, "upsert_incident", lambda item: upserted.append(item))

    seeded = incident_catalog_seed.ensure_mock_incidents_seeded()

    assert len(seeded) == 5
    assert len(upserted) == 5
    assert seeded[0]["incidentId"] == "MOCK-INC-001"
    assert seeded[-1]["incidentName"] == "IncidentE"


def test_ensure_mock_incidents_seeded_only_inserts_missing_items(monkeypatch):
    upserted: list[dict] = []

    monkeypatch.setattr(
        incident_catalog_seed,
        "list_all_incidents",
        lambda: [{"incidentId": "MOCK-INC-001"}, {"incidentId": "REAL-INC-001"}],
    )
    monkeypatch.setattr(incident_catalog_seed, "upsert_incident", lambda item: upserted.append(item))

    seeded = incident_catalog_seed.ensure_mock_incidents_seeded()

    assert len(seeded) == 4
    assert all(item["incidentId"] != "MOCK-INC-001" for item in upserted)
