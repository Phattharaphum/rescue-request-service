from src.application.usecases.create_rescue_request import _validate_request_type
from src.domain.enums.request_type import RequestType


def test_request_type_allows_only_current_operational_categories():
    assert [item.value for item in RequestType] == ["MEDICAL", "EVACUATION", "SUPPLY"]


def test_request_type_rejects_legacy_disaster_categories():
    assert _validate_request_type("FLOOD") == [{
        "field": "requestType",
        "issue": "must be one of: MEDICAL, EVACUATION, SUPPLY",
    }]
