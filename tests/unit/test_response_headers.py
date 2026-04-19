import json

from src.handlers.handler_utils import handle_error
from src.shared.errors import ValidationError
from src.shared.response import ALLOWED_ORIGINS, apply_cors_headers, ok


def test_ok_response_includes_access_control_allow_origin():
    response = ok({"status": "ok"})

    assert response["headers"]["Access-Control-Allow-Origin"] == ALLOWED_ORIGINS[0]


def test_handle_error_includes_access_control_allow_origin():
    event = {
        "path": "/v1/rescue-requests",
        "httpMethod": "POST",
        "requestContext": {"requestId": "gateway-request-id"},
    }
    response = handle_error(
        ValidationError("Input validation failed", [{"field": "x", "issue": "bad"}]),
        event,
    )

    body = json.loads(response["body"])

    assert response["headers"]["Access-Control-Allow-Origin"] == ALLOWED_ORIGINS[0]
    assert response["headers"]["X-Trace-Id"] == body["traceId"]
    assert body["errorCode"] == "VALIDATION_ERROR"
    assert body["path"] == "/v1/rescue-requests"
    assert body["method"] == "POST"
    assert body["requestId"] == "gateway-request-id"
    assert body["details"] == [{"field": "x", "issue": "bad"}]


def test_apply_cors_headers_reflects_allowed_request_origin():
    response = apply_cors_headers(
        ok({"status": "ok"}),
        {"headers": {"origin": "http://localhost:3000"}},
    )

    assert response["headers"]["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert response["headers"]["Vary"] == "Origin"
