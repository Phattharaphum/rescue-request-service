from src.adapters.persistence.rescue_request_repository import get_current_state, get_master, list_events
from src.adapters.utils.masking import mask_phone
from src.shared.errors import NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str, contact_phone: str | None = None, tracking_code: str | None = None) -> dict:
    master = get_master(request_id)
    current = get_current_state(request_id)
    if not master or not current:
        raise NotFoundError(f"Request {request_id} not found")

    current_version = current.get("stateVersion")
    events_result = list_events(request_id=request_id, limit=20, order="DESC")
    all_events = [_clean_event_item(e) for e in events_result.get("items", [])]
    if isinstance(current_version, int):
        bounded = [e for e in all_events if isinstance(e.get("version"), int) and e["version"] <= current_version]
    else:
        bounded = all_events
    recent_events = bounded[:5] if bounded else all_events[:5]
    latest_event = next(
        (e for e in recent_events if e.get("version") == current_version),
        recent_events[0] if recent_events else None,
    )
    status = current.get("status")

    return {
        "requestId": request_id,
        "incidentId": master.get("incidentId"),
        "requestType": master.get("requestType"),
        "status": status,
        "statusMessage": _status_message(status),
        "nextSuggestedAction": _next_suggested_action(status),
        "description": master.get("description"),
        "peopleCount": master.get("peopleCount"),
        "specialNeeds": master.get("specialNeeds"),
        "submittedAt": master.get("submittedAt"),
        "lastCitizenUpdateAt": master.get("lastCitizenUpdateAt"),
        "contactName": master.get("contactName"),
        "contactPhoneMasked": mask_phone(master.get("contactPhone", "")),
        "location": {
            "latitude": master.get("latitude"),
            "longitude": master.get("longitude"),
            "locationDetails": master.get("locationDetails"),
            "addressLine": master.get("addressLine"),
            "province": master.get("province"),
            "district": master.get("district"),
            "subdistrict": master.get("subdistrict"),
        },
        "priorityLevel": current.get("priorityLevel"),
        "assignedUnitId": current.get("assignedUnitId"),
        "assignedAt": current.get("assignedAt"),
        "latestNote": current.get("latestNote"),
        "lastUpdatedAt": current.get("lastUpdatedAt"),
        "stateVersion": current.get("stateVersion"),
        "latestEvent": latest_event,
        "recentEvents": recent_events,
    }


def _clean_event_item(item: dict) -> dict:
    return {
        "eventId": item.get("eventId"),
        "version": item.get("version"),
        "previousStatus": item.get("previousStatus"),
        "newStatus": item.get("newStatus"),
        "occurredAt": item.get("occurredAt"),
        "changeReason": item.get("changeReason"),
        "meta": item.get("meta"),
        "priorityScore": item.get("priorityScore"),
        "responderUnitId": item.get("responderUnitId"),
    }


def _status_message(status: str | None) -> str | None:
    messages = {
        "SUBMITTED": "ระบบรับคำร้องแล้วและรอเจ้าหน้าที่คัดแยก",
        "TRIAGED": "เจ้าหน้าที่คัดแยกคำร้องแล้ว กำลังเตรียมมอบหมายหน่วยช่วยเหลือ",
        "ASSIGNED": "มีการมอบหมายหน่วยช่วยเหลือแล้ว กรุณาติดตามการอัปเดตล่าสุด",
        "IN_PROGRESS": "หน่วยช่วยเหลือกำลังเข้าดำเนินการ",
        "RESOLVED": "คำร้องนี้เสร็จสิ้นแล้ว",
        "CANCELLED": "คำร้องนี้ถูกยกเลิก",
    }
    return messages.get(status)


def _next_suggested_action(status: str | None) -> str | None:
    suggestions = {
        "SUBMITTED": "อยู่ในพื้นที่ปลอดภัยและเตรียมช่องทางติดต่อไว้",
        "TRIAGED": "ติดตามสถานะเป็นระยะ หากข้อมูลเปลี่ยนให้ส่งอัปเดตเพิ่มเติม",
        "ASSIGNED": "เตรียมพร้อมรับการติดต่อจากหน่วยช่วยเหลือ",
        "IN_PROGRESS": "ปฏิบัติตามคำแนะนำของเจ้าหน้าที่ในพื้นที่",
        "RESOLVED": "หากยังต้องการความช่วยเหลือเพิ่มเติม ให้เปิดคำร้องใหม่",
        "CANCELLED": "หากยังต้องการความช่วยเหลือ ให้เปิดคำร้องใหม่",
    }
    return suggestions.get(status)
