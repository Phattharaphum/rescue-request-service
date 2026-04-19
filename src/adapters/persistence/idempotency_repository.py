from decimal import Decimal
from typing import Any

from src.adapters.persistence.dynamodb_client import get_dynamodb_resource
from src.shared.config import IDEMPOTENCY_TABLE_NAME
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _get_table():
    return get_dynamodb_resource().Table(IDEMPOTENCY_TABLE_NAME)


def _convert_decimals(obj):
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    return obj


def reserve_idempotency_key(record: dict) -> bool:
    table = _get_table()
    try:
        table.put_item(
            Item=record,
            ConditionExpression="attribute_not_exists(idempotencyKeyHash)",
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def reclaim_expired_in_progress_idempotency_key(
    *,
    key_hash: str,
    request_fingerprint: str,
    operation_name: str,
    resource_scope: str,
    expected_lock_expires_at: str,
    now_iso: str,
    lock_owner: str,
    locked_at: str,
    lock_expires_at: str,
    updated_at: str,
    expires_at: int,
) -> bool:
    table = _get_table()
    expr_names = {"#status": "status"}
    expr_values: dict[str, Any] = {
        ":in_progress": "IN_PROGRESS",
        ":request_fingerprint": request_fingerprint,
        ":operation_name": operation_name,
        ":resource_scope": resource_scope,
        ":expected_lock_expires_at": expected_lock_expires_at,
        ":now_iso": now_iso,
        ":lock_owner": lock_owner,
        ":locked_at": locked_at,
        ":lock_expires_at": lock_expires_at,
        ":updated_at": updated_at,
        ":expires_at": expires_at,
    }
    try:
        table.update_item(
            Key={"idempotencyKeyHash": key_hash},
            ConditionExpression=(
                "#status = :in_progress "
                "AND requestFingerprint = :request_fingerprint "
                "AND operationName = :operation_name "
                "AND resourceScope = :resource_scope "
                "AND lockExpiresAt = :expected_lock_expires_at "
                "AND lockExpiresAt <= :now_iso"
            ),
            UpdateExpression=(
                "SET #status = :in_progress, "
                "lockOwner = :lock_owner, "
                "lockedAt = :locked_at, "
                "lockExpiresAt = :lock_expires_at, "
                "updatedAt = :updated_at, "
                "expiresAt = :expires_at "
                "REMOVE errorCode, errorMessage"
            ),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def retry_failed_idempotency_key(
    *,
    key_hash: str,
    request_fingerprint: str,
    operation_name: str,
    resource_scope: str,
    lock_owner: str,
    locked_at: str,
    lock_expires_at: str,
    updated_at: str,
    expires_at: int,
) -> bool:
    table = _get_table()
    expr_names = {"#status": "status"}
    expr_values: dict[str, Any] = {
        ":failed": "FAILED",
        ":in_progress": "IN_PROGRESS",
        ":request_fingerprint": request_fingerprint,
        ":operation_name": operation_name,
        ":resource_scope": resource_scope,
        ":lock_owner": lock_owner,
        ":locked_at": locked_at,
        ":lock_expires_at": lock_expires_at,
        ":updated_at": updated_at,
        ":expires_at": expires_at,
    }
    try:
        table.update_item(
            Key={"idempotencyKeyHash": key_hash},
            ConditionExpression=(
                "#status = :failed "
                "AND requestFingerprint = :request_fingerprint "
                "AND operationName = :operation_name "
                "AND resourceScope = :resource_scope"
            ),
            UpdateExpression=(
                "SET #status = :in_progress, "
                "lockOwner = :lock_owner, "
                "lockedAt = :locked_at, "
                "lockExpiresAt = :lock_expires_at, "
                "updatedAt = :updated_at, "
                "expiresAt = :expires_at "
                "REMOVE errorCode, errorMessage"
            ),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def get_idempotency_record(key_hash: str) -> dict | None:
    table = _get_table()
    resp = table.get_item(Key={"idempotencyKeyHash": key_hash})
    item = resp.get("Item")
    return _convert_decimals(item) if item else None


def finalize_idempotency_key(
    key_hash: str,
    status: str,
    response_status_code: int | None = None,
    response_body: str | None = None,
    result_resource_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    updated_at: str = "",
    expected_lock_owner: str | None = None,
) -> bool:
    table = _get_table()
    update_parts = ["#status = :status", "updatedAt = :updated_at"]
    expr_values: dict[str, Any] = {":status": status, ":updated_at": updated_at}
    expr_names = {"#status": "status"}

    if response_status_code is not None:
        update_parts.append("responseStatusCode = :rsc")
        expr_values[":rsc"] = response_status_code
    if response_body is not None:
        update_parts.append("responseBody = :rb")
        expr_values[":rb"] = response_body
    if result_resource_id is not None:
        update_parts.append("resultResourceId = :rri")
        expr_values[":rri"] = result_resource_id
    if error_code is not None:
        update_parts.append("errorCode = :ec")
        expr_values[":ec"] = error_code
    if error_message is not None:
        update_parts.append("errorMessage = :em")
        expr_values[":em"] = error_message

    kwargs: dict[str, Any] = {
        "Key": {"idempotencyKeyHash": key_hash},
        "UpdateExpression": "SET " + ", ".join(update_parts),
        "ExpressionAttributeValues": expr_values,
        "ExpressionAttributeNames": expr_names,
    }
    if expected_lock_owner:
        kwargs["ConditionExpression"] = "#status = :in_progress AND lockOwner = :expected_lock_owner"
        kwargs["ExpressionAttributeValues"][":in_progress"] = "IN_PROGRESS"
        kwargs["ExpressionAttributeValues"][":expected_lock_owner"] = expected_lock_owner

    try:
        table.update_item(**kwargs)
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False
