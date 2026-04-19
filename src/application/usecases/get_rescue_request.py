from src.adapters.persistence.rescue_request_repository import (
    get_current_state,
    get_master,
    list_citizen_updates,
    list_events,
)
from src.application.usecases.current_state_projection import clean_current_state_item
from src.shared.errors import NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str, include_events: bool = False, include_citizen_updates: bool = False) -> dict:
    master = get_master(request_id)
    if not master:
        raise NotFoundError(f"Request {request_id} not found")

    current = get_current_state(request_id)

    result = {
        "master": _clean_item(master),
        "currentState": clean_current_state_item(current) if current else None,
    }

    updates_result = list_citizen_updates(request_id, limit=100)
    update_items = [_clean_update_item(u) for u in updates_result["items"]]
    result["updateItems"] = update_items

    if include_events:
        events_result = list_events(request_id, limit=100)
        result["events"] = [_clean_item(e) for e in events_result["items"]]

    if include_citizen_updates:
        # Backward-compatible alias for older clients.
        result["citizenUpdates"] = update_items

    return result


def _clean_item(item: dict) -> dict:
    exclude_keys = {"PK", "SK", "itemType"}
    return {k: v for k, v in item.items() if k not in exclude_keys}


def _clean_update_item(item: dict) -> dict:
    allowed_fields = {
        "updateId",
        "requestId",
        "updateType",
        "updatePayload",
        "citizenAuthMethod",
        "createdAt",
    }
    return {k: v for k, v in item.items() if k in allowed_fields}
