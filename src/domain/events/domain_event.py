from dataclasses import dataclass
from typing import Any


@dataclass
class DomainEvent:
    event_type: str
    body: dict[str, Any]
    partition_key: str
    correlation_id: str | None = None
    trace_id: str | None = None
