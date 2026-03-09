from dataclasses import dataclass
from typing import Any


@dataclass
class StatusEvent:
    event_id: str
    request_id: str
    previous_status: str | None
    new_status: str
    changed_by: str
    changed_by_role: str
    change_reason: str | None = None
    meta: dict[str, Any] | None = None
    priority_score: float | None = None
    responder_unit_id: str | None = None
    version: int = 1
    occurred_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "requestId": self.request_id,
            "previousStatus": self.previous_status,
            "newStatus": self.new_status,
            "changedBy": self.changed_by,
            "changedByRole": self.changed_by_role,
            "changeReason": self.change_reason,
            "meta": self.meta,
            "priorityScore": self.priority_score,
            "responderUnitId": self.responder_unit_id,
            "version": self.version,
            "occurredAt": self.occurred_at,
        }
