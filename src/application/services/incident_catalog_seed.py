from datetime import datetime, timezone

from src.adapters.persistence.incident_catalog_repository import list_all_incidents, upsert_incident

MOCK_INCIDENTS = [
    {
        "incidentId": "f3e1c8b2-6a1d-4c22-a9f3-5f8b7a1d2e10",
        "incidentType": "flood",
        "incidentName": "Bang Rak Flash Flood - Charoen Krung Corridor",
        "incidentSequence": 1,
        "status": "ACTIVE",
        "incidentDescription": "Rapidly rising floodwater in low-lying lanes around Charoen Krung Road; multiple households reported trapped residents awaiting boat evacuation.",
    },
    {
        "incidentId": "9a0d7b34-2f6e-4b87-8d1a-3c7f5e2a9b44",
        "incidentType": "fire",
        "incidentName": "Samut Prakan Warehouse Fire - Soi Sukhumvit 77",
        "incidentSequence": 2,
        "status": "ACTIVE",
        "incidentDescription": "Structure fire involving stacked packaging materials inside a medium-size warehouse; dense smoke affecting nearby residential blocks.",
    },
    {
        "incidentId": "2c4f9e71-8b55-4d6a-b3a1-1e7f0c4d8a22",
        "incidentType": "medical",
        "incidentName": "Chiang Mai Heatwave Medical Surge",
        "incidentSequence": 3,
        "status": "REPORTED",
        "incidentDescription": "Multiple heat exhaustion and dehydration cases reported during prolonged high temperatures; emergency medical teams requested for community triage points.",
    },
    {
        "incidentId": "7d2a1b5c-3e44-45f8-9c12-6b0e3f9d7a61",
        "incidentType": "storm",
        "incidentName": "Nakhon Si Thammarat Tropical Storm Monitoring",
        "incidentSequence": 4,
        "status": "MONITORING",
        "incidentDescription": "Tropical storm band approaching coastal districts with risk of fallen trees and localized flash flooding; response teams on standby.",
    },
    {
        "incidentId": "c1b8e3d4-5f92-4a7c-8d6e-2f0a9b3c7d58",
        "incidentType": "evacuation",
        "incidentName": "Rayong Industrial Chemical Leak Evacuation",
        "incidentSequence": 5,
        "status": "REPORTED",
        "incidentDescription": "Suspected solvent leak from an industrial storage area; precautionary evacuation initiated for nearby worker housing and schools.",
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
