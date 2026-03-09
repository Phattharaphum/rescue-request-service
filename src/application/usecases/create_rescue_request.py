import json
import uuid
from datetime import datetime, timezone

from src.adapters.messaging.sns_publisher import publish_event
from src.adapters.persistence.rescue_request_repository import create_rescue_request
from src.adapters.utils.hashing import hash_phone, hash_tracking_code
from src.adapters.utils.phone_normalizer import normalize_phone
from src.application.services.duplicate_detection_service import detect_duplicate, get_duplicate_signature
from src.application.services.event_publisher import publish_request_created
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.request_status import RequestStatus
from src.domain.value_objects.tracking_code import generate_tracking_code
from src.shared.errors import ConflictError, ValidationError
from src.shared.logger import get_logger
from src.shared.validators import validate_latitude, validate_longitude, validate_phone, validate_required_fields

logger = get_logger(__name__)

REQUIRED_FIELDS = [
    "incidentId", "requestType", "description", "peopleCount",
    "latitude", "longitude", "contactName", "contactPhone", "sourceChannel",
]


def execute(body: dict, idempotency_key: str | None = None, client_ip: str | None = None, user_agent: str | None = None) -> dict:
    errors = validate_required_fields(body, REQUIRED_FIELDS)
    errors.extend(validate_phone(body.get("contactPhone", "")))
    errors.extend(validate_latitude(body.get("latitude")))
    errors.extend(validate_longitude(body.get("longitude")))
    if errors:
        raise ValidationError("Input validation failed", errors)

    if idempotency_key:
        replay = check_and_reserve(
            idempotency_key=idempotency_key,
            operation_name="CreateRescueRequest",
            request_body=body,
            client_id=None,
            request_ip=client_ip,
            user_agent=user_agent,
        )
        if replay and replay.get("replay"):
            return json.loads(replay["body"])

    now = datetime.now(timezone.utc).isoformat()
    request_id = str(uuid.uuid4())

    if not idempotency_key:
        existing_id = detect_duplicate(
            incident_id=body["incidentId"],
            contact_phone=body["contactPhone"],
            request_type=body["requestType"],
            latitude=float(body["latitude"]),
            longitude=float(body["longitude"]),
            submitted_at=now,
        )
        if existing_id:
            raise ConflictError(
                "Duplicate request detected",
                [{"field": "request", "issue": f"existing request: {existing_id}"}],
            )

    normalized_phone = normalize_phone(body["contactPhone"])
    phone_hash = hash_phone(normalized_phone)
    tracking_code = generate_tracking_code()
    tc_hash = hash_tracking_code(tracking_code)

    dup_signature = get_duplicate_signature(
        incident_id=body["incidentId"],
        contact_phone=body["contactPhone"],
        request_type=body["requestType"],
        latitude=float(body["latitude"]),
        longitude=float(body["longitude"]),
        submitted_at=now,
    )

    event_id = str(uuid.uuid4())

    master_item = {
        "PK": f"REQ#{request_id}",
        "SK": "META",
        "itemType": "MASTER",
        "requestId": request_id,
        "incidentId": body["incidentId"],
        "requestType": body["requestType"],
        "description": body["description"],
        "peopleCount": int(body["peopleCount"]),
        "specialNeeds": body.get("specialNeeds"),
        "latitude": float(body["latitude"]),
        "longitude": float(body["longitude"]),
        "locationDetails": body.get("locationDetails"),
        "province": body.get("province"),
        "district": body.get("district"),
        "subdistrict": body.get("subdistrict"),
        "addressLine": body.get("addressLine"),
        "contactName": body["contactName"],
        "contactPhone": body["contactPhone"],
        "contactPhoneNormalized": normalized_phone,
        "contactPhoneHash": phone_hash,
        "trackingCodeHash": tc_hash,
        "sourceChannel": body["sourceChannel"],
        "submittedAt": now,
        "lastCitizenUpdateAt": None,
    }

    current_item = {
        "PK": f"REQ#{request_id}",
        "SK": "CURRENT",
        "itemType": "CURRENT_STATE",
        "requestId": request_id,
        "incidentId": body["incidentId"],
        "lastEventId": event_id,
        "stateVersion": 1,
        "status": RequestStatus.SUBMITTED.value,
        "priorityScore": None,
        "priorityLevel": None,
        "assignedUnitId": None,
        "assignedAt": None,
        "latestNote": None,
        "lastUpdatedBy": "system",
        "lastUpdatedAt": now,
    }

    event_item = {
        "PK": f"REQ#{request_id}",
        "SK": "EVENT#0000000001",
        "itemType": "STATUS_EVENT",
        "eventId": event_id,
        "requestId": request_id,
        "previousStatus": None,
        "newStatus": RequestStatus.SUBMITTED.value,
        "changedBy": "system",
        "changedByRole": "system",
        "changeReason": "Initial submission",
        "meta": None,
        "priorityScore": None,
        "responderUnitId": None,
        "version": 1,
        "occurredAt": now,
    }

    tracking_item = {
        "PK": f"TRACK#{phone_hash}",
        "SK": f"CODE#{tc_hash}",
        "itemType": "TRACKING_LOOKUP",
        "phoneHash": phone_hash,
        "trackingCodeHash": tc_hash,
        "requestId": request_id,
        "incidentId": body["incidentId"],
        "createdAt": now,
    }

    incident_item = {
        "PK": f"INCIDENT#{body['incidentId']}",
        "SK": f"REQUEST#{now}#{request_id}",
        "itemType": "INCIDENT_PROJECTION",
        "requestId": request_id,
        "incidentId": body["incidentId"],
        "status": RequestStatus.SUBMITTED.value,
        "requestType": body["requestType"],
        "contactName": body["contactName"],
        "submittedAt": now,
    }

    duplicate_item = {
        "PK": f"DUP#{dup_signature}",
        "SK": f"REQUEST#{request_id}",
        "itemType": "DUPLICATE_SIGNATURE",
        "requestId": request_id,
        "signature": dup_signature,
        "createdAt": now,
    }

    try:
        create_rescue_request(
            master_item=master_item,
            current_item=current_item,
            event_item=event_item,
            tracking_item=tracking_item,
            incident_item=incident_item,
            duplicate_item=duplicate_item,
        )
    except Exception as e:
        if idempotency_key:
            finalize_failure(idempotency_key, "CREATE_FAILED", str(e))
        raise

    result = {
        "requestId": request_id,
        "trackingCode": tracking_code,
        "status": RequestStatus.SUBMITTED.value,
        "submittedAt": now,
    }

    if idempotency_key:
        finalize_success(
            idempotency_key=idempotency_key,
            response_status_code=201,
            response_body=json.dumps(result, default=str),
            result_resource_id=request_id,
        )

    try:
        publish_request_created(request_id=request_id, request_data=master_item, correlation_id=request_id)
    except Exception:
        logger.exception("Failed to publish request created event")

    return result
