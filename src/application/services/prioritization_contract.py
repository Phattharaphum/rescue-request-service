from copy import deepcopy

from src.domain.enums.update_type import UpdateType


def build_prioritization_snapshot(master_record: dict) -> dict:
    snapshot = {
        "requestId": master_record.get("requestId"),
        "incidentId": master_record.get("incidentId"),
        "requestType": master_record.get("requestType"),
        "description": master_record.get("description"),
        "peopleCount": master_record.get("peopleCount"),
        "location": {
            "latitude": master_record.get("latitude"),
            "longitude": master_record.get("longitude"),
            "province": master_record.get("province"),
            "district": master_record.get("district"),
            "subdistrict": master_record.get("subdistrict"),
            "addressLine": master_record.get("addressLine"),
        },
        "submittedAt": master_record.get("submittedAt"),
    }

    special_needs = _normalize_special_needs(master_record.get("specialNeeds"))
    if special_needs:
        snapshot["specialNeeds"] = special_needs

    location_details = master_record.get("locationDetails")
    if location_details:
        # Contract v1 does not document this field, but the current service already stores it.
        snapshot["locationDetails"] = location_details

    return snapshot


def apply_patch_updates_to_master(master_record: dict, updates: dict) -> dict:
    merged = deepcopy(master_record)
    merged.update(updates)
    return merged


def apply_citizen_update_to_master(master_record: dict, update_type: UpdateType, update_payload: dict) -> dict:
    merged = deepcopy(master_record)

    if update_type == UpdateType.PEOPLE_COUNT:
        merged["peopleCount"] = update_payload.get("peopleCount")
    elif update_type == UpdateType.SPECIAL_NEEDS:
        merged["specialNeeds"] = update_payload.get("specialNeeds")
    elif update_type == UpdateType.LOCATION_DETAILS:
        merged["locationDetails"] = update_payload.get("locationDetails")

    return merged


def requires_re_evaluation_for_update_type(update_type: UpdateType) -> bool:
    return update_type in {
        UpdateType.LOCATION_DETAILS,
        UpdateType.PEOPLE_COUNT,
        UpdateType.SPECIAL_NEEDS,
    }


def _normalize_special_needs(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return None
