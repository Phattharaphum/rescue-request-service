import uuid
from datetime import datetime, timezone
from typing import Any

from src.shared.config import SERVICE_NAME


def build_envelope(
    event_type: str,
    body: dict[str, Any],
    partition_key: str,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return {
        "header": {
            "messageId": str(uuid.uuid4()),
            "eventType": event_type,
            "schemaVersion": "1.0",
            "producer": SERVICE_NAME,
            "occurredAt": datetime.now(timezone.utc).isoformat(),
            "traceId": trace_id or str(uuid.uuid4()),
            "correlationId": correlation_id or str(uuid.uuid4()),
            "partitionKey": partition_key,
            "contentType": "application/json",
        },
        "body": body,
    }
