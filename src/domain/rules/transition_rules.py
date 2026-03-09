from src.domain.enums.request_status import RequestStatus
from src.shared.errors import ConflictError, ValidationError

ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.SUBMITTED: {RequestStatus.TRIAGED, RequestStatus.CANCELLED},
    RequestStatus.TRIAGED: {RequestStatus.ASSIGNED, RequestStatus.CANCELLED},
    RequestStatus.ASSIGNED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.IN_PROGRESS: {RequestStatus.RESOLVED, RequestStatus.CANCELLED},
    RequestStatus.RESOLVED: set(),
    RequestStatus.CANCELLED: set(),
}


def validate_transition(current_status: RequestStatus, new_status: RequestStatus) -> None:
    if RequestStatus.is_terminal(current_status):
        raise ConflictError(
            f"Cannot transition from terminal state {current_status.value}",
            [{"field": "status", "issue": f"current status {current_status.value} is terminal"}],
        )

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ConflictError(
            f"Invalid transition from {current_status.value} to {new_status.value}",
            [{"field": "status", "issue": f"transition from {current_status.value} to {new_status.value} is not allowed"}],
        )


def validate_transition_requirements(new_status: RequestStatus, payload: dict) -> None:
    if new_status == RequestStatus.ASSIGNED:
        if not payload.get("responderUnitId"):
            raise ValidationError(
                "responderUnitId is required for ASSIGNED status",
                [{"field": "responderUnitId", "issue": "is required when transitioning to ASSIGNED"}],
            )
    if new_status == RequestStatus.CANCELLED:
        if not payload.get("reason"):
            raise ValidationError(
                "reason is required for CANCELLED status",
                [{"field": "reason", "issue": "is required when cancelling a request"}],
            )
