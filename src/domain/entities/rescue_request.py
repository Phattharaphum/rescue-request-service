from dataclasses import dataclass, field
from typing import Any


@dataclass
class RescueRequest:
    request_id: str
    incident_id: str
    request_type: str
    description: str
    people_count: int
    special_needs: str | None
    latitude: float
    longitude: float
    location_details: str | None
    province: str | None
    district: str | None
    subdistrict: str | None
    address_line: str | None
    contact_name: str
    contact_phone: str
    contact_phone_normalized: str
    contact_phone_hash: str
    tracking_code_hash: str
    source_channel: str
    submitted_at: str
    last_citizen_update_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "incidentId": self.incident_id,
            "requestType": self.request_type,
            "description": self.description,
            "peopleCount": self.people_count,
            "specialNeeds": self.special_needs,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "locationDetails": self.location_details,
            "province": self.province,
            "district": self.district,
            "subdistrict": self.subdistrict,
            "addressLine": self.address_line,
            "contactName": self.contact_name,
            "contactPhone": self.contact_phone,
            "contactPhoneNormalized": self.contact_phone_normalized,
            "contactPhoneHash": self.contact_phone_hash,
            "trackingCodeHash": self.tracking_code_hash,
            "sourceChannel": self.source_channel,
            "submittedAt": self.submitted_at,
            "lastCitizenUpdateAt": self.last_citizen_update_at,
        }
