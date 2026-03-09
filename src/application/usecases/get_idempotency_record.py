from src.adapters.persistence.idempotency_repository import get_idempotency_record
from src.adapters.utils.hashing import hash_idempotency_key
from src.shared.errors import NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(idempotency_key_hash: str, include_response: bool = False, include_fingerprint: bool = False) -> dict:
    record = get_idempotency_record(idempotency_key_hash)
    if not record:
        raise NotFoundError(f"Idempotency key not found")

    result = {
        "idempotencyKeyHash": record.get("idempotencyKeyHash"),
        "operationName": record.get("operationName"),
        "status": record.get("status"),
        "createdAt": record.get("createdAt"),
        "updatedAt": record.get("updatedAt"),
        "resultResourceId": record.get("resultResourceId"),
    }

    if include_response:
        result["responseStatusCode"] = record.get("responseStatusCode")
        result["responseBody"] = record.get("responseBody")

    if include_fingerprint:
        result["requestFingerprint"] = record.get("requestFingerprint")

    return result
