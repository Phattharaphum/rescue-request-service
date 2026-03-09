from src.adapters.messaging.sns_publisher import publish_event
from src.shared.logger import get_logger

logger = get_logger(__name__)


def publish_request_created(request_id: str, request_data: dict, correlation_id: str | None = None) -> None:
    publish_event(
        event_type="rescue-request.created",
        body={"requestId": request_id, "data": request_data},
        partition_key=request_id,
        correlation_id=correlation_id,
    )


def publish_status_changed(
    request_id: str,
    previous_status: str,
    new_status: str,
    event_id: str,
    version: int,
    correlation_id: str | None = None,
) -> None:
    publish_event(
        event_type="rescue-request.status-changed",
        body={
            "requestId": request_id,
            "previousStatus": previous_status,
            "newStatus": new_status,
            "eventId": event_id,
            "version": version,
        },
        partition_key=request_id,
        correlation_id=correlation_id,
    )


def publish_citizen_updated(request_id: str, update_id: str, update_type: str, correlation_id: str | None = None) -> None:
    publish_event(
        event_type="rescue-request.citizen-updated",
        body={"requestId": request_id, "updateId": update_id, "updateType": update_type},
        partition_key=request_id,
        correlation_id=correlation_id,
    )


def publish_resolved(request_id: str, event_id: str, correlation_id: str | None = None) -> None:
    publish_event(
        event_type="rescue-request.resolved",
        body={"requestId": request_id, "eventId": event_id},
        partition_key=request_id,
        correlation_id=correlation_id,
    )


def publish_cancelled(request_id: str, event_id: str, reason: str, correlation_id: str | None = None) -> None:
    publish_event(
        event_type="rescue-request.cancelled",
        body={"requestId": request_id, "eventId": event_id, "reason": reason},
        partition_key=request_id,
        correlation_id=correlation_id,
    )
