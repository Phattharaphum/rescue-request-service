from src.adapters.persistence.incident_catalog_repository import list_incidents


def execute(limit: int = 20, cursor: str | None = None, status: str | None = None) -> dict:
    result = list_incidents(limit=limit, cursor=cursor, status=status)
    return {
        "items": [_clean_item(item) for item in result["items"]],
        "nextCursor": result.get("nextCursor"),
    }


def _clean_item(item: dict) -> dict:
    excluded = {"catalogPartition", "catalogSortKey"}
    return {key: value for key, value in item.items() if key not in excluded}
