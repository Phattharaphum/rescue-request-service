import hashlib


def hash_phone(normalized_phone: str) -> str:
    return hashlib.sha256(f"phone:{normalized_phone}".encode("utf-8")).hexdigest()


def hash_tracking_code(tracking_code: str) -> str:
    return hashlib.sha256(f"tracking:{tracking_code}".encode("utf-8")).hexdigest()


def hash_idempotency_key(key: str) -> str:
    return hashlib.sha256(f"idempotency:{key}".encode("utf-8")).hexdigest()


def hash_scoped_idempotency_key(key: str, scope: str) -> str:
    return hashlib.sha256(f"idempotency:{scope}:{key}".encode("utf-8")).hexdigest()


def hash_request_fingerprint(payload_json: str) -> str:
    return hashlib.sha256(f"fingerprint:{payload_json}".encode("utf-8")).hexdigest()
