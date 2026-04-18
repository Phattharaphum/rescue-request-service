from src.adapters.persistence.incident_catalog_repository import list_incidents
from src.application.services.incident_catalog_seed import ensure_mock_incidents_seeded


def execute(limit: int = 20, cursor: str | None = None, status: str | None = None) -> dict:
    ensure_mock_incidents_seeded()
    result = list_incidents(limit=limit, cursor=cursor, status=status)
    return {
        "items": [_clean_item(item) for item in result["items"]],
        "nextCursor": result.get("nextCursor"),
    }


def _clean_item(item: dict) -> dict:
    excluded = {"catalogPartition", "catalogSortKey"}
    return {key: value for key, value in item.items() if key not in excluded}
