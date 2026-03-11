import re
import math
import uuid as uuid_module
from typing import Any

from src.shared.errors import BadRequestError, ValidationError


def validate_required_fields(data: dict[str, Any], fields: list[str]) -> list[dict[str, str]]:
    errors = []
    for field in fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            errors.append({"field": field, "issue": "is required"})
    return errors


def validate_uuid(value: str, field_name: str = "id") -> str:
    try:
        uuid_module.UUID(value)
        return value
    except (ValueError, AttributeError):
        raise BadRequestError(f"Invalid UUID format for {field_name}", [{"field": field_name, "issue": "must be a valid UUID"}])


def validate_phone(phone: str) -> list[dict[str, str]]:
    errors = []
    if not isinstance(phone, str) or not phone or not re.match(r"^[\d\+\-\s\(\)]{7,20}$", phone):
        errors.append({"field": "contactPhone", "issue": "invalid phone number format"})
    return errors


def validate_latitude(lat: Any) -> list[dict[str, str]]:
    errors = []
    try:
        lat_f = float(lat)
        if not math.isfinite(lat_f):
            errors.append({"field": "latitude", "issue": "must be a finite number"})
            return errors
        if lat_f < -90 or lat_f > 90:
            errors.append({"field": "latitude", "issue": "must be between -90 and 90"})
    except (TypeError, ValueError):
        errors.append({"field": "latitude", "issue": "must be a valid number"})
    return errors


def validate_longitude(lon: Any) -> list[dict[str, str]]:
    errors = []
    try:
        lon_f = float(lon)
        if not math.isfinite(lon_f):
            errors.append({"field": "longitude", "issue": "must be a finite number"})
            return errors
        if lon_f < -180 or lon_f > 180:
            errors.append({"field": "longitude", "issue": "must be between -180 and 180"})
    except (TypeError, ValueError):
        errors.append({"field": "longitude", "issue": "must be a valid number"})
    return errors


def validate_pagination(limit: Any = None, cursor: Any = None) -> tuple[int, str | None]:
    parsed_limit = 20
    if limit is not None:
        try:
            parsed_limit = int(limit)
            if parsed_limit < 1 or parsed_limit > 100:
                raise BadRequestError("limit must be between 1 and 100")
        except (TypeError, ValueError):
            raise BadRequestError("limit must be a valid integer")
    parsed_cursor = cursor if cursor else None
    return parsed_limit, parsed_cursor
