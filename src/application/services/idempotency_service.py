import json
import uuid
from datetime import datetime, timedelta, timezone

from src.adapters.persistence.idempotency_repository import (
    finalize_idempotency_key,
    get_idempotency_record,
    reserve_idempotency_key,
)
from src.adapters.utils.fingerprint import compute_request_fingerprint
from src.adapters.utils.hashing import hash_idempotency_key
from src.shared.config import IDEMPOTENCY_TTL_HOURS
from src.shared.errors import ConflictError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def check_and_reserve(
    idempotency_key: str,
    operation_name: str,
    request_body: dict,
    client_id: str | None = None,
    request_ip: str | None = None,
    user_agent: str | None = None,
) -> dict | None:
    key_hash = hash_idempotency_key(idempotency_key)
    fingerprint = compute_request_fingerprint(request_body)
    now = datetime.now(timezone.utc)

    existing = get_idempotency_record(key_hash)
    if existing:
        if existing.get("requestFingerprint") != fingerprint:
            raise ConflictError(
                "Idempotency key already used with different payload",
                [{"field": "X-Idempotency-Key", "issue": "key reused with different request body"}],
            )
        if existing.get("status") == "COMPLETED":
            return {
                "replay": True,
                "statusCode": existing.get("responseStatusCode", 200),
                "body": existing.get("responseBody", "{}"),
                "resultResourceId": existing.get("resultResourceId"),
            }
        if existing.get("status") == "IN_PROGRESS":
            raise ConflictError("Request is already being processed")
        return None

    record = {
        "idempotencyKeyHash": key_hash,
        "operationName": operation_name,
        "requestFingerprint": fingerprint,
        "status": "IN_PROGRESS",
        "lockOwner": str(uuid.uuid4()),
        "lockedAt": now.isoformat(),
        "lockExpiresAt": (now + timedelta(minutes=5)).isoformat(),
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
        "expiresAt": int((now + timedelta(hours=IDEMPOTENCY_TTL_HOURS)).timestamp()),
        "clientId": client_id,
        "requestIp": request_ip,
        "userAgent": user_agent,
    }
    reserved = reserve_idempotency_key(record)
    if not reserved:
        return check_and_reserve(idempotency_key, operation_name, request_body, client_id, request_ip, user_agent)
    return None


def finalize_success(
    idempotency_key: str,
    response_status_code: int,
    response_body: str,
    result_resource_id: str | None = None,
) -> None:
    key_hash = hash_idempotency_key(idempotency_key)
    now = datetime.now(timezone.utc).isoformat()
    finalize_idempotency_key(
        key_hash=key_hash,
        status="COMPLETED",
        response_status_code=response_status_code,
        response_body=response_body,
        result_resource_id=result_resource_id,
        updated_at=now,
    )


def finalize_failure(
    idempotency_key: str,
    error_code: str,
    error_message: str,
) -> None:
    key_hash = hash_idempotency_key(idempotency_key)
    now = datetime.now(timezone.utc).isoformat()
    finalize_idempotency_key(
        key_hash=key_hash,
        status="FAILED",
        error_code=error_code,
        error_message=error_message,
        updated_at=now,
    )
