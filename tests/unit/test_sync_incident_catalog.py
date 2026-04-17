from src.application.usecases import sync_incident_catalog as usecase


def test_assigns_running_incident_names_and_reuses_existing(monkeypatch):
    upserted: list[dict] = []

    monkeypatch.setattr(
        usecase,
        "fetch_incidents",
        lambda: [
            {
                "incident_id": "INC-001",
                "incident_type": "fire",
                "incident_description": "Existing incident updated",
                "status": "REPORTED",
                "created_at": "2026-02-22T00:00:00Z",
                "updated_at": "2026-02-22T00:01:04Z",
            },
            {
                "incident_id": "INC-002",
                "incident_type": "flood",
                "incident_description": "New incident",
                "status": "ACTIVE",
                "created_at": "2026-02-22T01:00:00Z",
                "updated_at": "2026-02-22T01:01:04Z",
            },
        ],
    )
    monkeypatch.setattr(
        usecase,
        "list_all_incidents",
        lambda: [{
            "incidentId": "INC-001",
            "incidentName": "IncidentA",
            "incidentSequence": 1,
        }],
    )
    monkeypatch.setattr(usecase, "get_next_incident_sequence", lambda: 2)
    monkeypatch.setattr(usecase, "upsert_incident", lambda item: upserted.append(item))

    result = usecase.execute()

    assert result["created"] == 1
    assert result["updated"] == 1
    assert upserted[0]["incidentName"] == "IncidentA"
    assert upserted[1]["incidentName"] == "IncidentB"


def test_generates_alphabetic_names_beyond_z():
    assert usecase._build_incident_name(1) == "IncidentA"
    assert usecase._build_incident_name(26) == "IncidentZ"
    assert usecase._build_incident_name(27) == "IncidentAA"
