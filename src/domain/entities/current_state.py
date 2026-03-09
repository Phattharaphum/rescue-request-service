from dataclasses import dataclass
from typing import Any


@dataclass
class CurrentState:
    request_id: str
    incident_id: str
    last_event_id: str
    state_version: int
    status: str
    priority_score: float | None = None
    priority_level: str | None = None
    assigned_unit_id: str | None = None
    assigned_at: str | None = None
    latest_note: str | None = None
    last_updated_by: str | None = None
    last_updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "incidentId": self.incident_id,
            "lastEventId": self.last_event_id,
            "stateVersion": self.state_version,
            "status": self.status,
            "priorityScore": self.priority_score,
            "priorityLevel": self.priority_level,
            "assignedUnitId": self.assigned_unit_id,
            "assignedAt": self.assigned_at,
            "latestNote": self.latest_note,
            "lastUpdatedBy": self.last_updated_by,
            "lastUpdatedAt": self.last_updated_at,
        }
