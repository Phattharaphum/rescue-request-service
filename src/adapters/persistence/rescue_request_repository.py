import json
from decimal import Decimal
from typing import Any

from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from src.adapters.persistence.dynamodb_client import get_dynamodb_resource
from src.adapters.utils.cursor import decode_cursor, encode_cursor
from src.shared.config import DYNAMODB_TABLE_NAME, STAGE
from src.shared.errors import ConflictError, NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)
_serializer = TypeSerializer()


def _get_table():
    return get_dynamodb_resource().Table(DYNAMODB_TABLE_NAME)


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


def _to_dynamodb_item(data: dict) -> dict:
    result = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, float):
            result[k] = Decimal(str(v))
        elif isinstance(v, dict):
            result[k] = json.loads(json.dumps(v), parse_float=Decimal)
        else:
            result[k] = v
    return result


def _to_dynamodb_attribute_map(data: dict) -> dict:
    """Convert Python values into low-level DynamoDB AttributeValue map for client APIs."""
    return {k: _serializer.serialize(v) for k, v in data.items()}


def _to_dynamodb_value(value: Any) -> Any:
    """Normalize a single Python value to a DynamoDB-serializable value."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, (dict, list)):
        return json.loads(json.dumps(value), parse_float=Decimal)
    return value


def _build_update_components(current_updates: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, Any], dict[str, Any]]:
    update_expr_parts: list[str] = []
    expr_attr_names: dict[str, str] = {}
    expr_attr_values_client: dict[str, Any] = {}
    expr_attr_values_resource: dict[str, Any] = {}

    for key, value in current_updates.items():
        safe_key = f"#k_{key}"
        safe_val = f":v_{key}"
        normalized = _to_dynamodb_value(value)
        expr_attr_names[safe_key] = key
        expr_attr_values_client[safe_val] = _serializer.serialize(normalized)
        expr_attr_values_resource[safe_val] = normalized
        update_expr_parts.append(f"{safe_key} = {safe_val}")

    return update_expr_parts, expr_attr_names, expr_attr_values_client, expr_attr_values_resource


def create_rescue_request(
    master_item: dict,
    current_item: dict,
    event_item: dict,
    tracking_item: dict,
    phone_unique_item: dict | None,
    incident_item: dict,
    duplicate_item: dict | None = None,
) -> None:
    table = _get_table()
    resource = get_dynamodb_resource()

    items = [master_item, current_item, event_item, tracking_item, incident_item]
    if phone_unique_item:
        items.append(phone_unique_item)
    if duplicate_item:
        items.append(duplicate_item)

    transact_items = []
    for item in items:
        transact_items.append({
            "Put": {
                "TableName": DYNAMODB_TABLE_NAME,
                "Item": _to_dynamodb_attribute_map(_to_dynamodb_item(item)),
            }
        })

    client = resource.meta.client
    try:
        client.transact_write_items(TransactItems=transact_items)
        return
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "TransactionCanceledException":
            logger.error(f"Transaction cancelled: {e}")
            raise ConflictError("Failed to create rescue request - transaction conflict")
        if STAGE == "local" and error_code == "ValidationException":
            # LocalStack can reject transaction payloads that real DynamoDB accepts.
            # Fallback keeps local development unblocked.
            logger.warning("Falling back to non-transactional local write for create_rescue_request")
            try:
                for item in items:
                    table.put_item(
                        Item=_to_dynamodb_item(item),
                        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
                    )
                return
            except ClientError as fallback_error:
                fallback_code = fallback_error.response.get("Error", {}).get("Code", "")
                if fallback_code == "ConditionalCheckFailedException":
                    raise ConflictError("Failed to create rescue request - transaction conflict")
                raise
        raise


def get_master(request_id: str) -> dict | None:
    table = _get_table()
    resp = table.get_item(Key={"PK": f"REQ#{request_id}", "SK": "META"})
    item = resp.get("Item")
    return _convert_decimals(item) if item else None


def get_current_state(request_id: str) -> dict | None:
    table = _get_table()
    resp = table.get_item(Key={"PK": f"REQ#{request_id}", "SK": "CURRENT"})
    item = resp.get("Item")
    return _convert_decimals(item) if item else None


def list_events(request_id: str, limit: int = 20, cursor: str | None = None,
                since_version: int | None = None, order: str = "ASC", sort_order: str | None = None) -> dict:
    table = _get_table()
    # Backward compatibility: allow legacy callers that still pass sort_order.
    resolved_order = sort_order if sort_order is not None else order
    if resolved_order.upper() not in ("ASC", "DESC"):
        raise ValueError(f"Invalid order: {resolved_order}. Must be 'ASC' or 'DESC'.")
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "ExpressionAttributeValues": {":pk": f"REQ#{request_id}", ":sk_prefix": "EVENT#"},
        "Limit": limit,
        "ScanIndexForward": resolved_order.upper() != "DESC",
    }
    if cursor:
        decoded = decode_cursor(cursor)
        if decoded:
            kwargs["ExclusiveStartKey"] = decoded
    if since_version is not None:
        kwargs["KeyConditionExpression"] = "PK = :pk AND SK >= :sk_start"
        kwargs["ExpressionAttributeValues"][":sk_start"] = f"EVENT#{since_version:010d}"

    resp = table.query(**kwargs)
    items = [_convert_decimals(i) for i in resp.get("Items", [])]
    next_cursor = None
    if resp.get("LastEvaluatedKey"):
        next_cursor = encode_cursor(resp["LastEvaluatedKey"])
    return {"items": items, "nextCursor": next_cursor}


def list_citizen_updates(request_id: str, limit: int = 20, cursor: str | None = None,
                         since: str | None = None) -> dict:
    table = _get_table()
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "ExpressionAttributeValues": {":pk": f"REQ#{request_id}", ":sk_prefix": "UPDATE#"},
        "Limit": limit,
        "ScanIndexForward": True,
    }
    if cursor:
        decoded = decode_cursor(cursor)
        if decoded:
            kwargs["ExclusiveStartKey"] = decoded
    if since:
        kwargs["KeyConditionExpression"] = "PK = :pk AND SK >= :sk_start"
        kwargs["ExpressionAttributeValues"][":sk_start"] = f"UPDATE#{since}"

    resp = table.query(**kwargs)
    items = [_convert_decimals(i) for i in resp.get("Items", [])]
    next_cursor = None
    if resp.get("LastEvaluatedKey"):
        next_cursor = encode_cursor(resp["LastEvaluatedKey"])
    return {"items": items, "nextCursor": next_cursor}


def tracking_lookup(phone_hash: str, tracking_code_hash: str) -> dict | None:
    table = _get_table()
    resp = table.get_item(Key={"PK": f"TRACK#{phone_hash}", "SK": f"CODE#{tracking_code_hash}"})
    item = resp.get("Item")
    return _convert_decimals(item) if item else None


def find_by_phone_hash(phone_hash: str) -> dict | None:
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"TRACK#{phone_hash}"},
        Limit=1,
    )
    items = resp.get("Items", [])
    return _convert_decimals(items[0]) if items else None


def list_by_incident(incident_id: str, limit: int = 20, cursor: str | None = None,
                     status: str | None = None) -> dict:
    table = _get_table()
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "ExpressionAttributeValues": {":pk": f"INCIDENT#{incident_id}", ":sk_prefix": "REQUEST#"},
        "Limit": limit,
        "ScanIndexForward": False,
    }
    if cursor:
        decoded = decode_cursor(cursor)
        if decoded:
            kwargs["ExclusiveStartKey"] = decoded

    resp = table.query(**kwargs)
    items = [_convert_decimals(i) for i in resp.get("Items", [])]
    next_cursor = None
    if resp.get("LastEvaluatedKey"):
        next_cursor = encode_cursor(resp["LastEvaluatedKey"])
    return {"items": items, "nextCursor": next_cursor}


def append_event_and_update_current(request_id: str, event_item: dict, current_updates: dict,
                                    expected_version: int | None = None) -> None:
    resource = get_dynamodb_resource()
    client = resource.meta.client
    table = _get_table()

    transact_items = [
        {
            "Put": {
                "TableName": DYNAMODB_TABLE_NAME,
                "Item": _to_dynamodb_attribute_map(_to_dynamodb_item(event_item)),
                "ConditionExpression": "attribute_not_exists(PK)",
            }
        },
    ]

    update_expr_parts, expr_attr_names, expr_attr_values, expr_attr_values_resource = _build_update_components(current_updates)

    update_item = {
        "Update": {
            "TableName": DYNAMODB_TABLE_NAME,
            "Key": {
                "PK": {"S": f"REQ#{request_id}"},
                "SK": {"S": "CURRENT"},
            },
            "UpdateExpression": "SET " + ", ".join(update_expr_parts),
            "ExpressionAttributeNames": expr_attr_names,
            "ExpressionAttributeValues": expr_attr_values,
        }
    }
    if expected_version is not None:
        update_item["Update"]["ConditionExpression"] = "stateVersion = :expected_version"
        update_item["Update"]["ExpressionAttributeValues"][":expected_version"] = {"N": str(expected_version)}
        expr_attr_values_resource[":expected_version"] = expected_version

    transact_items.append(update_item)

    try:
        client.transact_write_items(TransactItems=transact_items)
        return
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "TransactionCanceledException":
            logger.error(f"Transition transaction cancelled: {e}")
            raise ConflictError("State transition conflict - concurrent modification detected")
        if STAGE == "local" and error_code == "ValidationException":
            # LocalStack can reject some transaction payloads that DynamoDB accepts.
            # Fallback keeps local development unblocked while preserving conditional checks.
            logger.warning("Falling back to non-transactional local write due to ValidationException")
            try:
                table.put_item(
                    Item=_to_dynamodb_item(event_item),
                    ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
                )
                resource_update_kwargs: dict[str, Any] = {
                    "Key": {"PK": f"REQ#{request_id}", "SK": "CURRENT"},
                    "UpdateExpression": "SET " + ", ".join(update_expr_parts),
                    "ExpressionAttributeNames": dict(expr_attr_names),
                    "ExpressionAttributeValues": dict(expr_attr_values_resource),
                }
                if expected_version is not None:
                    resource_update_kwargs["ConditionExpression"] = "#cv = :expected_version"
                    resource_update_kwargs["ExpressionAttributeNames"]["#cv"] = "stateVersion"
                table.update_item(**resource_update_kwargs)
                return
            except ClientError as fallback_error:
                fallback_code = fallback_error.response.get("Error", {}).get("Code", "")
                if fallback_code == "ConditionalCheckFailedException":
                    raise ConflictError("State transition conflict - concurrent modification detected")
                raise
        raise


def put_citizen_update(item: dict) -> None:
    table = _get_table()
    table.put_item(Item=_to_dynamodb_item(item))


def update_master_fields(request_id: str, updates: dict, expected_version: int | None = None) -> None:
    table = _get_table()
    update_parts = []
    expr_values = {}
    expr_names = {}

    for key, value in updates.items():
        safe_key = f"#k_{key}"
        safe_val = f":v_{key}"
        expr_names[safe_key] = key
        expr_values[safe_val] = value if not isinstance(value, float) else Decimal(str(value))
        update_parts.append(f"{safe_key} = {safe_val}")

    kwargs: dict[str, Any] = {
        "Key": {"PK": f"REQ#{request_id}", "SK": "META"},
        "UpdateExpression": "SET " + ", ".join(update_parts),
        "ExpressionAttributeNames": expr_names,
        "ExpressionAttributeValues": expr_values,
        "ConditionExpression": "attribute_exists(PK)",
    }

    table.update_item(**kwargs)


def check_duplicate_signature(signature: str) -> dict | None:
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"DUP#{signature}"},
        Limit=1,
    )
    items = resp.get("Items", [])
    return _convert_decimals(items[0]) if items else None
