from decimal import Decimal
from typing import Any

from src.adapters.persistence.dynamodb_client import get_dynamodb_resource
from src.adapters.utils.cursor import decode_cursor, encode_cursor
from src.shared.config import INCIDENT_CATALOG_TABLE_NAME

CATALOG_PARTITION = "CATALOG"
CATALOG_INDEX_NAME = "CatalogOrderIndex"


def _get_table():
    return get_dynamodb_resource().Table(INCIDENT_CATALOG_TABLE_NAME)


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


def get_incident(incident_id: str) -> dict | None:
    response = _get_table().get_item(Key={"incidentId": incident_id})
    item = response.get("Item")
    return _convert_decimals(item) if item else None


def get_next_incident_sequence() -> int:
    response = _get_table().query(
        IndexName=CATALOG_INDEX_NAME,
        KeyConditionExpression="catalogPartition = :catalog_partition",
        ExpressionAttributeValues={":catalog_partition": CATALOG_PARTITION},
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return 1
    current = _convert_decimals(items[0]).get("incidentSequence", 0)
    return int(current) + 1


def list_all_incidents() -> list[dict]:
    table = _get_table()
    items: list[dict] = []
    last_evaluated_key = None

    while True:
        kwargs: dict[str, Any] = {}
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = table.scan(**kwargs)
        items.extend(_convert_decimals(item) for item in response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return items


def list_incidents(limit: int = 20, cursor: str | None = None, status: str | None = None) -> dict:
    kwargs: dict[str, Any] = {
        "IndexName": CATALOG_INDEX_NAME,
        "KeyConditionExpression": "catalogPartition = :catalog_partition",
        "ExpressionAttributeValues": {":catalog_partition": CATALOG_PARTITION},
        "Limit": limit,
        "ScanIndexForward": True,
    }
    if status:
        kwargs["FilterExpression"] = "#status = :status"
        kwargs["ExpressionAttributeNames"] = {"#status": "status"}
        kwargs["ExpressionAttributeValues"][":status"] = status
    if cursor:
        decoded = decode_cursor(cursor)
        if decoded:
            kwargs["ExclusiveStartKey"] = decoded

    response = _get_table().query(**kwargs)
    items = [_convert_decimals(item) for item in response.get("Items", [])]
    next_cursor = None
    if response.get("LastEvaluatedKey"):
        next_cursor = encode_cursor(response["LastEvaluatedKey"])
    return {"items": items, "nextCursor": next_cursor}


def upsert_incident(item: dict) -> None:
    _get_table().put_item(Item=item)
