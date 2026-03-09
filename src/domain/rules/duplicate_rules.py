import hashlib

from src.adapters.utils.geohash import encode_geohash
from src.adapters.utils.phone_normalizer import normalize_phone
from src.shared.config import DUPLICATE_TIME_BUCKET_MINUTES


def build_duplicate_signature(
    incident_id: str,
    contact_phone: str,
    request_type: str,
    latitude: float,
    longitude: float,
    submitted_at: str,
) -> str:
    normalized_phone = normalize_phone(contact_phone)
    geo = encode_geohash(latitude, longitude, precision=7)
    time_bucket = _compute_time_bucket(submitted_at)
    raw = f"{incident_id}|{normalized_phone}|{request_type}|{geo}|{time_bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compute_time_bucket(iso_timestamp: str) -> str:
    from datetime import datetime
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    bucket_minutes = (dt.hour * 60 + dt.minute) // DUPLICATE_TIME_BUCKET_MINUTES * DUPLICATE_TIME_BUCKET_MINUTES
    return f"{dt.strftime('%Y-%m-%d')}T{bucket_minutes // 60:02d}:{bucket_minutes % 60:02d}"
