import json
import uuid
from datetime import datetime, timezone

from src.adapters.persistence.incident_catalog_repository import get_incident
from src.adapters.persistence.rescue_request_repository import (
    create_rescue_request,
    find_by_phone_hash,
    update_current_fields,
)
from src.adapters.utils.hashing import hash_phone, hash_tracking_code
from src.adapters.utils.phone_normalizer import normalize_phone
from src.application.services.duplicate_detection_service import detect_duplicate, get_duplicate_signature
from src.application.services.event_publisher import publish_request_created
from src.application.services.idempotency_service import check_and_reserve, finalize_failure, finalize_success
from src.domain.enums.request_status import RequestStatus
from src.domain.enums.request_type import RequestType
from src.domain.enums.source_channel import SourceChannel
from src.domain.value_objects.tracking_code import generate_tracking_code
from src.shared.errors import ConflictError, ValidationError
from src.shared.logger import get_logger
from src.shared.validators import validate_latitude, validate_longitude, validate_phone, validate_required_fields

logger = get_logger(__name__)

REQUIRED_FIELDS = [
    "incidentId",
    "requestType",
    "description",
    "peopleCount",
    "latitude",
    "longitude",
    "contactName",
    "contactPhone",
    "sourceChannel",
]


def execute(
    body: dict, idempotency_key: str | None = None, client_ip: str | None = None, user_agent: str | None = None
) -> dict:
    errors = validate_required_fields(body, REQUIRED_FIELDS)
    errors.extend(validate_phone(body.get("contactPhone", "")))
    errors.extend(validate_latitude(body.get("latitude")))
    errors.extend(validate_longitude(body.get("longitude")))
    errors.extend(_validate_request_type(body.get("requestType")))
    errors.extend(_validate_source_channel(body.get("sourceChannel")))
    errors.extend(_validate_people_count(body.get("peopleCount")))
    if errors:
        raise ValidationError("Input validation failed", errors)

    latitude = float(body["latitude"])
    longitude = float(body["longitude"])
    people_count = int(body["peopleCount"])

    idempotency_reservation: dict | None = None
    if idempotency_key:
        idempotency_reservation = check_and_reserve(
            idempotency_key=idempotency_key,
            operation_name="CreateRescueRequest",
            resource_scope="POST:/v1/rescue-requests",
            request_body=body,
            client_id=None,
            request_ip=client_ip,
            user_agent=user_agent,
        )
        if idempotency_reservation and idempotency_reservation.get("replay"):
            return json.loads(idempotency_reservation["body"])

    incident = get_incident(body["incidentId"])
    if not incident:
        raise ValidationError(
            "Input validation failed",
            [{"field": "incidentId", "issue": "must reference an existing incident in IncidentCatalogTable"}],
        )

    normalized_phone = normalize_phone(body["contactPhone"])
    phone_hash = hash_phone(normalized_phone)
    existing_phone_request = find_by_phone_hash(phone_hash)
    if existing_phone_request:
        raise ConflictError(
            "contactPhone already has an existing request",
            [{"field": "contactPhone", "issue": f"existing request: {existing_phone_request.get('requestId')}"}],
        )

    now = datetime.now(timezone.utc).isoformat()
    request_id = str(uuid.uuid4())

    if not idempotency_key:
        existing_id = detect_duplicate(
            incident_id=body["incidentId"],
            contact_phone=body["contactPhone"],
            request_type=body["requestType"],
            latitude=latitude,
            longitude=longitude,
            submitted_at=now,
        )
        if existing_id:
            raise ConflictError(
                "Duplicate request detected",
                [{"field": "request", "issue": f"existing request: {existing_id}"}],
            )

    tracking_code = generate_tracking_code()
    tc_hash = hash_tracking_code(tracking_code)

    dup_signature = get_duplicate_signature(
        incident_id=body["incidentId"],
        contact_phone=body["contactPhone"],
        request_type=body["requestType"],
        latitude=latitude,
        longitude=longitude,
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
        "peopleCount": people_count,
        "specialNeeds": body.get("specialNeeds"),
        "latitude": latitude,
        "longitude": longitude,
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
        "latestPrioritySourceEventId": None,
        "latestPrioritySourceEventType": None,
        "latestPrioritySourceOccurredAt": None,
        "latestPriorityEvaluationId": None,
        "latestPriorityReason": None,
        "latestPriorityEvaluatedAt": None,
        "latestPriorityCorrelationId": None,
        "lastPriorityIngestedAt": None,
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

    phone_unique_item = {
        "PK": f"PHONE#{phone_hash}",
        "SK": "UNIQUE",
        "itemType": "PHONE_UNIQUE",
        "phoneHash": phone_hash,
        "requestId": request_id,
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
            phone_unique_item=phone_unique_item,
            incident_item=incident_item,
            duplicate_item=duplicate_item,
        )
    except Exception as e:
        if idempotency_key:
            finalize_failure(
                idempotency_key=idempotency_key,
                error_code="CREATE_FAILED",
                error_message=str(e),
                idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
                lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
            )
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
            idempotency_key_hash=idempotency_reservation.get("keyHash") if idempotency_reservation else None,
            lock_owner=idempotency_reservation.get("lockOwner") if idempotency_reservation else None,
        )

    try:
        header = publish_request_created(request_id=request_id, request_data=master_item, correlation_id=request_id)
        if header:
            update_current_fields(
                request_id=request_id,
                updates={
                    "latestPrioritySourceEventId": header["messageId"],
                    "latestPrioritySourceEventType": header["eventType"],
                    "latestPrioritySourceOccurredAt": header["occurredAt"],
                },
            )
    except Exception:
        logger.exception("Failed to publish request created event")

    return result


def _validate_request_type(value: str | None) -> list[dict[str, str]]:
    if value is None:
        return []
    try:
        RequestType(value)
        return []
    except (ValueError, TypeError):
        return [{"field": "requestType", "issue": f"must be one of: {', '.join(v.value for v in RequestType)}"}]


def _validate_source_channel(value: str | None) -> list[dict[str, str]]:
    if value is None:
        return []
    try:
        SourceChannel(value)
        return []
    except (ValueError, TypeError):
        return [{"field": "sourceChannel", "issue": f"must be one of: {', '.join(v.value for v in SourceChannel)}"}]


def _validate_people_count(value) -> list[dict[str, str]]:
    if isinstance(value, bool):
        return [{"field": "peopleCount", "issue": "must be an integer greater than 0"}]
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return [{"field": "peopleCount", "issue": "must be an integer greater than 0"}]
    if parsed < 1:
        return [{"field": "peopleCount", "issue": "must be an integer greater than 0"}]
    # DynamoDB Number supports up to 38 digits of precision.
    if len(str(abs(parsed))) > 38:
        return [{"field": "peopleCount", "issue": "must be within DynamoDB numeric limits"}]
    return []
