import json
import uuid

from src.handlers.staff.list_status_events import handler


def test_list_status_events_invalid_order_returns_standard_bad_request():
    event = {
        "httpMethod": "GET",
        "path": "/v1/rescue-requests/test/events",
        "headers": {},
        "body": None,
        "pathParameters": {"requestId": str(uuid.uuid4())},
        "queryStringParameters": {"order": "SIDEWAYS"},
        "requestContext": {"requestId": "req-order-invalid"},
    }

    response = handler(event, None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["errorCode"] == "BAD_REQUEST"
    assert body["message"] == "order must be ASC or DESC"
    assert body["requestId"] == "req-order-invalid"
