from datetime import datetime, timezone

from src.adapters.persistence.incident_catalog_repository import list_all_incidents, upsert_incident

MOCK_INCIDENTS = [
    {
        "incidentId": "MOCK-INC-001",
        "incidentType": "flood",
        "incidentName": "IncidentA",
        "incidentSequence": 1,
        "status": "REPORTED",
        "incidentDescription": "Mock flood incident for internal testing and UI bootstrap",
    },
    {
        "incidentId": "MOCK-INC-002",
        "incidentType": "fire",
        "incidentName": "IncidentB",
        "incidentSequence": 2,
        "status": "ACTIVE",
        "incidentDescription": "Mock fire incident for internal testing and UI bootstrap",
    },
    {
        "incidentId": "MOCK-INC-003",
        "incidentType": "medical",
        "incidentName": "IncidentC",
        "incidentSequence": 3,
        "status": "REPORTED",
        "incidentDescription": "Mock medical support incident for internal testing and UI bootstrap",
    },
    {
        "incidentId": "MOCK-INC-004",
        "incidentType": "storm",
        "incidentName": "IncidentD",
        "incidentSequence": 4,
        "status": "MONITORING",
        "incidentDescription": "Mock storm incident for internal testing and UI bootstrap",
    },
    {
        "incidentId": "MOCK-INC-005",
        "incidentType": "evacuation",
        "incidentName": "IncidentE",
        "incidentSequence": 5,
        "status": "ACTIVE",
        "incidentDescription": "Mock evacuation incident for internal testing and UI bootstrap",
    },
]


def ensure_mock_incidents_seeded() -> list[dict]:
    existing_items = {item.get("incidentId"): item for item in list_all_incidents() if item.get("incidentId")}
    seeded_items: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for mock in MOCK_INCIDENTS:
        incident_id = mock["incidentId"]
        if incident_id in existing_items:
            continue

        item = {
            **mock,
            "remoteCreatedAt": None,
            "remoteUpdatedAt": None,
            "lastSyncedAt": now,
            "catalogPartition": "CATALOG",
            "catalogSortKey": f"{mock['incidentSequence']:06d}#{incident_id}",
        }
        upsert_incident(item)
        seeded_items.append(item)

    return seeded_items
