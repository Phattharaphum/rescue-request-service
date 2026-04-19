import uuid
from datetime import datetime, timedelta, timezone

from src.adapters.persistence.idempotency_repository import (
    finalize_idempotency_key,
    get_idempotency_record,
    reclaim_expired_in_progress_idempotency_key,
    reserve_idempotency_key,
    retry_failed_idempotency_key,
)
from src.adapters.utils.fingerprint import compute_request_fingerprint
from src.adapters.utils.hashing import hash_idempotency_key, hash_scoped_idempotency_key
from src.shared.config import IDEMPOTENCY_TTL_HOURS
from src.shared.errors import ConflictError
from src.shared.logger import get_logger

logger = get_logger(__name__)


_MAX_RESERVE_RETRIES = 3
_LOCK_TIMEOUT_MINUTES = 5
_DEFAULT_RESOURCE_SCOPE = "GLOBAL"


def _normalize_resource_scope(resource_scope: str | None) -> str:
    if not isinstance(resource_scope, str):
        return _DEFAULT_RESOURCE_SCOPE
    normalized = resource_scope.strip()
    return normalized or _DEFAULT_RESOURCE_SCOPE


def _build_scope_key(operation_name: str, resource_scope: str | None) -> tuple[str, str]:
    normalized_scope = _normalize_resource_scope(resource_scope)
    scope_key = f"{operation_name}:{normalized_scope}"
    return scope_key, normalized_scope


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_lock_expired(lock_expires_at: str | None, now: datetime) -> bool:
    parsed = _parse_iso_datetime(lock_expires_at)
    if parsed is None:
        return False
    return parsed <= now


def _retry_reservation(
    *,
    idempotency_key: str,
    operation_name: str,
    resource_scope: str | None,
    request_body: dict,
    client_id: str | None,
    request_ip: str | None,
    user_agent: str | None,
    retry_count: int,
) -> dict:
    if retry_count >= _MAX_RESERVE_RETRIES:
        raise ConflictError("Unable to reserve idempotency key after multiple attempts")
    return check_and_reserve(
        idempotency_key=idempotency_key,
        operation_name=operation_name,
        resource_scope=resource_scope,
        request_body=request_body,
        client_id=client_id,
        request_ip=request_ip,
        user_agent=user_agent,
        _retry_count=retry_count + 1,
    )


def check_and_reserve(
    idempotency_key: str,
    operation_name: str,
    resource_scope: str | None,
    request_body: dict,
    client_id: str | None = None,
    request_ip: str | None = None,
    user_agent: str | None = None,
    _retry_count: int = 0,
) -> dict:
    scope_key, normalized_scope = _build_scope_key(operation_name, resource_scope)
    key_hash = hash_scoped_idempotency_key(idempotency_key, scope_key)
    fingerprint = compute_request_fingerprint(request_body)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    lock_owner = str(uuid.uuid4())
    lock_expires_at = (now + timedelta(minutes=_LOCK_TIMEOUT_MINUTES)).isoformat()

    existing = get_idempotency_record(key_hash)
    if existing:
        if existing.get("requestFingerprint") != fingerprint:
            raise ConflictError(
                "Idempotency key already used with different payload",
                [{"field": "X-Idempotency-Key", "issue": "key reused with different request body"}],
            )
        status = existing.get("status")
        if status == "COMPLETED":
            return {
                "replay": True,
                "statusCode": existing.get("responseStatusCode", 200),
                "body": existing.get("responseBody", "{}"),
                "resultResourceId": existing.get("resultResourceId"),
                "keyHash": key_hash,
            }
        if status == "IN_PROGRESS":
            if not _is_lock_expired(existing.get("lockExpiresAt"), now):
                raise ConflictError("Request is already being processed")

            reclaimed = reclaim_expired_in_progress_idempotency_key(
                key_hash=key_hash,
                request_fingerprint=fingerprint,
                operation_name=operation_name,
                resource_scope=normalized_scope,
                expected_lock_expires_at=existing.get("lockExpiresAt", ""),
                now_iso=now_iso,
                lock_owner=lock_owner,
                locked_at=now_iso,
                lock_expires_at=lock_expires_at,
                updated_at=now_iso,
                expires_at=int((now + timedelta(hours=IDEMPOTENCY_TTL_HOURS)).timestamp()),
            )
            if reclaimed:
                return {
                    "replay": False,
                    "lockOwner": lock_owner,
                    "keyHash": key_hash,
                }
            return _retry_reservation(
                idempotency_key=idempotency_key,
                operation_name=operation_name,
                resource_scope=normalized_scope,
                request_body=request_body,
                client_id=client_id,
                request_ip=request_ip,
                user_agent=user_agent,
                retry_count=_retry_count,
            )
        if status == "FAILED":
            retried = retry_failed_idempotency_key(
                key_hash=key_hash,
                request_fingerprint=fingerprint,
                operation_name=operation_name,
                resource_scope=normalized_scope,
                lock_owner=lock_owner,
                locked_at=now_iso,
                lock_expires_at=lock_expires_at,
                updated_at=now_iso,
                expires_at=int((now + timedelta(hours=IDEMPOTENCY_TTL_HOURS)).timestamp()),
            )
            if retried:
                return {
                    "replay": False,
                    "lockOwner": lock_owner,
                    "keyHash": key_hash,
                }
            return _retry_reservation(
                idempotency_key=idempotency_key,
                operation_name=operation_name,
                resource_scope=normalized_scope,
                request_body=request_body,
                client_id=client_id,
                request_ip=request_ip,
                user_agent=user_agent,
                retry_count=_retry_count,
            )
        raise ConflictError("Idempotency record is in unsupported state")

    record = {
        "idempotencyKeyHash": key_hash,
        "operationName": operation_name,
        "resourceScope": normalized_scope,
        "scopeKey": scope_key,
        "requestFingerprint": fingerprint,
        "status": "IN_PROGRESS",
        "lockOwner": lock_owner,
        "lockedAt": now_iso,
        "lockExpiresAt": lock_expires_at,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "expiresAt": int((now + timedelta(hours=IDEMPOTENCY_TTL_HOURS)).timestamp()),
        "clientId": client_id,
        "requestIp": request_ip,
        "userAgent": user_agent,
    }
    reserved = reserve_idempotency_key(record)
    if not reserved:
        return _retry_reservation(
            idempotency_key=idempotency_key,
            operation_name=operation_name,
            resource_scope=normalized_scope,
            request_body=request_body,
            client_id=client_id,
            request_ip=request_ip,
            user_agent=user_agent,
            retry_count=_retry_count,
        )
    return {
        "replay": False,
        "lockOwner": lock_owner,
        "keyHash": key_hash,
    }


def finalize_success(
    idempotency_key: str,
    response_status_code: int,
    response_body: str,
    result_resource_id: str | None = None,
    idempotency_key_hash: str | None = None,
    lock_owner: str | None = None,
) -> bool:
    key_hash = idempotency_key_hash or hash_idempotency_key(idempotency_key)
    now = datetime.now(timezone.utc).isoformat()
    finalized = finalize_idempotency_key(
        key_hash=key_hash,
        status="COMPLETED",
        response_status_code=response_status_code,
        response_body=response_body,
        result_resource_id=result_resource_id,
        updated_at=now,
        expected_lock_owner=lock_owner,
    )
    if not finalized:
        logger.warning("Skipping idempotency finalize_success due to lock ownership mismatch")
    return finalized


def finalize_failure(
    idempotency_key: str,
    error_code: str,
    error_message: str,
    idempotency_key_hash: str | None = None,
    lock_owner: str | None = None,
) -> bool:
    key_hash = idempotency_key_hash or hash_idempotency_key(idempotency_key)
    now = datetime.now(timezone.utc).isoformat()
    finalized = finalize_idempotency_key(
        key_hash=key_hash,
        status="FAILED",
        error_code=error_code,
        error_message=error_message,
        updated_at=now,
        expected_lock_owner=lock_owner,
    )
    if not finalized:
        logger.warning("Skipping idempotency finalize_failure due to lock ownership mismatch")
    return finalized
