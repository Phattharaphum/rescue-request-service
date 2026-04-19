from src.adapters.persistence.incident_catalog_repository import list_all_incidents
from src.application.services.incident_catalog_seed import ensure_mock_incidents_seeded


def execute() -> dict:
    ensure_mock_incidents_seeded()
    items = sorted(
        list_all_incidents(),
        key=lambda item: (
            int(item.get("incidentSequence", 0) or 0),
            str(item.get("incidentId") or ""),
        ),
    )
    return {
        "items": [_map_item(item) for item in items],
    }


def _map_item(item: dict) -> dict:
    return {
        "incident_id": item.get("incidentId"),
        "incident_type": item.get("incidentType"),
        "incident_name": item.get("incidentName"),
        "status": item.get("status"),
        "incident_description": item.get("incidentDescription"),
    }
