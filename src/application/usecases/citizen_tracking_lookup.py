from src.adapters.persistence.rescue_request_repository import tracking_lookup
from src.adapters.utils.hashing import hash_phone, hash_tracking_code
from src.adapters.utils.phone_normalizer import normalize_phone
from src.shared.errors import ForbiddenError, ValidationError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(contact_phone: str, tracking_code: str) -> dict:
    if not contact_phone or not tracking_code:
        raise ValidationError(
            "contactPhone and trackingCode are required",
            [
                {"field": "contactPhone", "issue": "is required"},
                {"field": "trackingCode", "issue": "is required"},
            ],
        )

    normalized = normalize_phone(contact_phone)
    phone_h = hash_phone(normalized)
    tc_h = hash_tracking_code(tracking_code)

    result = tracking_lookup(phone_h, tc_h)
    if not result:
        raise ForbiddenError("Invalid phone number or tracking code")

    return {
        "requestId": result.get("requestId"),
        "incidentId": result.get("incidentId"),
    }
