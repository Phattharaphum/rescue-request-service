from src.adapters.persistence.rescue_request_repository import get_current_state, get_master, tracking_lookup
from src.adapters.utils.hashing import hash_phone, hash_tracking_code
from src.adapters.utils.phone_normalizer import normalize_phone
from src.shared.errors import ForbiddenError, NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str, contact_phone: str | None = None, tracking_code: str | None = None) -> dict:
    current = get_current_state(request_id)
    if not current:
        raise NotFoundError(f"Request {request_id} not found")

    return {
        "requestId": request_id,
        "status": current.get("status"),
        "priorityLevel": current.get("priorityLevel"),
        "assignedUnitId": current.get("assignedUnitId"),
        "lastUpdatedAt": current.get("lastUpdatedAt"),
        "stateVersion": current.get("stateVersion"),
    }
