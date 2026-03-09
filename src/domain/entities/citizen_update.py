from dataclasses import dataclass
from typing import Any


@dataclass
class CitizenUpdate:
    update_id: str
    request_id: str
    update_type: str
    update_payload: dict[str, Any]
    citizen_auth_method: str | None = None
    citizen_phone_hash: str | None = None
    tracking_code_hash: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "updateId": self.update_id,
            "requestId": self.request_id,
            "updateType": self.update_type,
            "updatePayload": self.update_payload,
            "citizenAuthMethod": self.citizen_auth_method,
            "citizenPhoneHash": self.citizen_phone_hash,
            "trackingCodeHash": self.tracking_code_hash,
            "clientIp": self.client_ip,
            "userAgent": self.user_agent,
            "createdAt": self.created_at,
        }
