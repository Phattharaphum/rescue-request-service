from datetime import datetime, timezone

from src.adapters.external.incident_tracking_client import fetch_incidents
from src.adapters.persistence.incident_catalog_repository import (
    get_next_incident_sequence,
    list_all_incidents,
    upsert_incident,
)
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute() -> dict:
    raw_incidents = fetch_incidents()
    existing_items = {item["incidentId"]: item for item in list_all_incidents() if item.get("incidentId")}
    next_sequence = get_next_incident_sequence()
    skipped = 0
    created = 0
    updated = 0
    synced_at = datetime.now(timezone.utc).isoformat()

    for raw_incident in raw_incidents:
        incident_id = raw_incident.get("incident_id")
        if not isinstance(incident_id, str) or not incident_id.strip():
            skipped += 1
            logger.warning("Skipping incident payload without incident_id")
            continue

        incident_id = incident_id.strip()
        existing = existing_items.get(incident_id)
        sequence = _resolve_sequence(existing, next_sequence)
        if existing is None:
            next_sequence += 1
            created += 1
        else:
            updated += 1

        incident_name = (existing or {}).get("incidentName") or _build_incident_name(sequence)
        item = {
            "incidentId": incident_id,
            "incidentType": raw_incident.get("incident_type"),
            "incidentName": incident_name,
            "incidentSequence": sequence,
            "status": raw_incident.get("status"),
            "incidentDescription": raw_incident.get("incident_description"),
            "remoteCreatedAt": raw_incident.get("created_at"),
            "remoteUpdatedAt": raw_incident.get("updated_at"),
            "lastSyncedAt": synced_at,
            "catalogPartition": "CATALOG",
            "catalogSortKey": f"{sequence:06d}#{incident_id}",
        }
        upsert_incident(item)
        existing_items[incident_id] = item

    return {
        "fetched": len(raw_incidents),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "syncedAt": synced_at,
    }


def _resolve_sequence(existing: dict | None, next_sequence: int) -> int:
    if existing and isinstance(existing.get("incidentSequence"), int):
        return existing["incidentSequence"]
    if existing and isinstance(existing.get("incidentSequence"), float):
        return int(existing["incidentSequence"])
    return next_sequence


def _build_incident_name(sequence: int) -> str:
    return f"Incident{_to_alpha(sequence)}"


def _to_alpha(sequence: int) -> str:
    value = sequence
    letters: list[str] = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters)) or "A"
