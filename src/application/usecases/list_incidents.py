from src.adapters.persistence.incident_catalog_repository import list_incidents

VISIBLE_INCIDENT_STATUSES = {"REPORTED", "DISPATCHED", "ON-SITE"}

def execute(status: str | None = None) -> dict:
    statuses = sorted(VISIBLE_INCIDENT_STATUSES)
    if status:
        statuses = [status] if status in VISIBLE_INCIDENT_STATUSES else []

    result = list_incidents(statuses=statuses)
    return {
        "items": [_clean_item(item) for item in result["items"]],
        "nextCursor": None,
    }


def _clean_item(item: dict) -> dict:
    excluded = {"catalogPartition", "catalogSortKey"}
    return {key: value for key, value in item.items() if key not in excluded}
