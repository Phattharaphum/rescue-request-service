from dataclasses import dataclass, field
from typing import Any


@dataclass
class IdempotencyRecord:
    idempotency_key_hash: str
    operation_name: str
    request_fingerprint: str
    status: str  # IN_PROGRESS, COMPLETED, FAILED
    lock_owner: str | None = None
    locked_at: str | None = None
    lock_expires_at: str | None = None
    response_status_code: int | None = None
    response_headers: dict[str, str] | None = None
    response_body: str | None = None
    result_resource_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""
    expires_at: str = ""
    client_id: str | None = None
    request_ip: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "idempotencyKeyHash": self.idempotency_key_hash,
            "operationName": self.operation_name,
            "requestFingerprint": self.request_fingerprint,
            "status": self.status,
            "lockOwner": self.lock_owner,
            "lockedAt": self.locked_at,
            "lockExpiresAt": self.lock_expires_at,
            "responseStatusCode": self.response_status_code,
            "responseHeaders": self.response_headers,
            "responseBody": self.response_body,
            "resultResourceId": self.result_resource_id,
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "expiresAt": self.expires_at,
            "clientId": self.client_id,
            "requestIp": self.request_ip,
            "userAgent": self.user_agent,
        }
