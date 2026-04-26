from src.adapters.persistence.incident_catalog_repository import delete_all_incidents, list_all_incidents
from src.adapters.persistence.rescue_request_repository import (
    delete_all_request_items,
    delete_requests_by_ids,
    list_request_master_refs,
)


def clear_incident_catalog(*, delete_requests: bool = False) -> dict:
    deleted_request_items = delete_all_request_items() if delete_requests else 0
    deleted_incidents = delete_all_incidents()
    return {
        "operation": "clear_incident_catalog",
        "deletedIncidents": deleted_incidents,
        "deletedRequestItems": deleted_request_items,
    }


def clear_requests() -> dict:
    deleted_request_items = delete_all_request_items()
    return {
        "operation": "clear_requests",
        "deletedRequestItems": deleted_request_items,
    }


def clear_all_data() -> dict:
    deleted_request_items = delete_all_request_items()
    deleted_incidents = delete_all_incidents()
    return {
        "operation": "clear_all_data",
        "deletedIncidents": deleted_incidents,
        "deletedRequestItems": deleted_request_items,
    }


def delete_orphaned_requests() -> dict:
    existing_incident_ids = {
        item["incidentId"]
        for item in list_all_incidents()
        if isinstance(item.get("incidentId"), str) and item["incidentId"].strip()
    }
    orphaned_request_ids = {
        item["requestId"]
        for item in list_request_master_refs()
        if isinstance(item.get("requestId"), str) and item.get("incidentId") not in existing_incident_ids
    }
    deleted_request_items = delete_requests_by_ids(orphaned_request_ids)
    return {
        "operation": "delete_orphaned_requests",
        "deletedRequests": len(orphaned_request_ids),
        "deletedRequestItems": deleted_request_items,
    }
