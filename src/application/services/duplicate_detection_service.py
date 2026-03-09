from src.adapters.persistence.rescue_request_repository import check_duplicate_signature
from src.domain.rules.duplicate_rules import build_duplicate_signature
from src.shared.errors import ConflictError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def detect_duplicate(
    incident_id: str,
    contact_phone: str,
    request_type: str,
    latitude: float,
    longitude: float,
    submitted_at: str,
) -> str | None:
    signature = build_duplicate_signature(
        incident_id=incident_id,
        contact_phone=contact_phone,
        request_type=request_type,
        latitude=latitude,
        longitude=longitude,
        submitted_at=submitted_at,
    )

    existing = check_duplicate_signature(signature)
    if existing:
        existing_request_id = existing.get("requestId", "")
        return existing_request_id
    return None


def get_duplicate_signature(
    incident_id: str,
    contact_phone: str,
    request_type: str,
    latitude: float,
    longitude: float,
    submitted_at: str,
) -> str:
    return build_duplicate_signature(
        incident_id=incident_id,
        contact_phone=contact_phone,
        request_type=request_type,
        latitude=latitude,
        longitude=longitude,
        submitted_at=submitted_at,
    )
