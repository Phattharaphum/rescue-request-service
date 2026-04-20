import json
import os
import uuid

import boto3
import pytest

os.environ["STAGE"] = "local"
os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:4566"
os.environ["AWS_REGION"] = "ap-southeast-1"
os.environ["DYNAMODB_TABLE_NAME"] = "RescueRequestTable"
os.environ["IDEMPOTENCY_TABLE_NAME"] = "IdempotencyTable"
os.environ["INCIDENT_CATALOG_TABLE_NAME"] = "IncidentCatalogTable"
os.environ["SNS_TOPIC_ARN"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.handlers.commands.cancel import handler as cancel_handler
from src.handlers.public.create_citizen_update import handler as create_update_handler
from src.handlers.public.create_rescue_request import handler as create_request_handler
from src.handlers.public.list_citizen_updates import handler as list_updates_handler
from src.handlers.staff.get_rescue_request import handler as get_request_handler


def _random_phone() -> str:
    return "08" + str(uuid.uuid4().int % 10**8).zfill(8)


def _create_tables():
    dynamodb = boto3.client("dynamodb", endpoint_url="http://localhost:4566", region_name="ap-southeast-1")
    tables = dynamodb.list_tables()["TableNames"]

    if "RescueRequestTable" not in tables:
        dynamodb.create_table(
            TableName="RescueRequestTable",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    if "IdempotencyTable" not in tables:
        dynamodb.create_table(
            TableName="IdempotencyTable",
            AttributeDefinitions=[
                {"AttributeName": "idempotencyKeyHash", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "idempotencyKeyHash", "KeyType": "HASH"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    if "IncidentCatalogTable" not in tables:
        dynamodb.create_table(
            TableName="IncidentCatalogTable",
            AttributeDefinitions=[
                {"AttributeName": "incidentId", "AttributeType": "S"},
                {"AttributeName": "catalogPartition", "AttributeType": "S"},
                {"AttributeName": "catalogSortKey", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "incidentId", "KeyType": "HASH"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "CatalogOrderIndex",
                "KeySchema": [
                    {"AttributeName": "catalogPartition", "KeyType": "HASH"},
                    {"AttributeName": "catalogSortKey", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )


def _ensure_incident_in_catalog(incident_id: str) -> None:
    boto3.resource("dynamodb", endpoint_url="http://localhost:4566", region_name="ap-southeast-1").Table(
        "IncidentCatalogTable"
    ).put_item(Item={
        "incidentId": incident_id,
        "incidentType": "flood",
        "incidentName": "Integration Incident",
        "status": "ACTIVE",
        "incidentDescription": "Seeded for citizen updates integration test",
    })


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    try:
        _create_tables()
    except Exception:
        pytest.skip("LocalStack DynamoDB not available")


def _create_request() -> tuple[str, str]:
    incident_id = f"incident-{uuid.uuid4()}"
    _ensure_incident_in_catalog(incident_id)
    body = {
        "incidentId": incident_id,
        "requestType": "FLOOD",
        "description": "Citizen update flow test",
        "peopleCount": 2,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "contactName": "Citizen Update User",
        "contactPhone": _random_phone(),
        "sourceChannel": "WEB",
        "locationDetails": "Old location",
    }
    event = {
        "httpMethod": "POST",
        "path": "/v1/rescue-requests",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
        "pathParameters": None,
        "queryStringParameters": None,
    }
    response = create_request_handler(event, None)
    assert response["statusCode"] == 201
    parsed = json.loads(response["body"])
    return parsed["requestId"], parsed["trackingCode"]


def _create_update(request_id: str, tracking_code: str, update_type: str, update_payload: dict) -> dict:
    event = {
        "httpMethod": "POST",
        "path": f"/v1/citizen/rescue-requests/{request_id}/updates",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"trackingCode": tracking_code, "updateType": update_type, "updatePayload": update_payload}),
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": None,
    }
    return create_update_handler(event, None)


def _list_updates(request_id: str, query: dict | None = None) -> dict:
    event = {
        "httpMethod": "GET",
        "path": f"/v1/citizen/rescue-requests/{request_id}/updates",
        "headers": {},
        "body": None,
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": query,
    }
    return list_updates_handler(event, None)


class TestCitizenUpdatesFlow:
    def test_post_and_get_updates_success_and_safe_shape(self):
        request_id, tracking_code = _create_request()

        create_response = _create_update(request_id, tracking_code, "PEOPLE_COUNT", {"peopleCount": 7})
        assert create_response["statusCode"] == 201

        list_response = _list_updates(request_id)
        assert list_response["statusCode"] == 200
        result = json.loads(list_response["body"])
        assert len(result["items"]) >= 1
        item = result["items"][-1]
        assert item["requestId"] == request_id
        assert item["updateType"] == "PEOPLE_COUNT"
        assert item["updatePayload"]["peopleCount"] == 7
        assert "userAgent" not in item
        assert "clientIp" not in item
        assert "citizenPhoneHash" not in item
        assert "trackingCodeHash" not in item

        get_event = {
            "httpMethod": "GET",
            "path": f"/v1/rescue-requests/{request_id}",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        get_response = get_request_handler(get_event, None)
        assert get_response["statusCode"] == 200
        get_result = json.loads(get_response["body"])
        assert get_result["master"]["peopleCount"] == 2
        assert get_result["master"]["lastCitizenUpdateAt"] is not None
        assert any(
            u["updateType"] == "PEOPLE_COUNT" and u["updatePayload"].get("peopleCount") == 7
            for u in get_result["updateItems"]
        )

        get_with_alias_event = dict(get_event)
        get_with_alias_event["queryStringParameters"] = {"includeCitizenUpdates": "true"}
        alias_response = get_request_handler(get_with_alias_event, None)
        assert alias_response["statusCode"] == 200
        alias_result = json.loads(alias_response["body"])
        assert alias_result["citizenUpdates"] == alias_result["updateItems"]

    def test_post_update_payload_validation(self):
        request_id, tracking_code = _create_request()
        create_response = _create_update(request_id, tracking_code, "PEOPLE_COUNT", {"peopleCount": 0})
        assert create_response["statusCode"] == 422

    def test_post_update_invalid_tracking_code(self):
        request_id, _ = _create_request()
        create_response = _create_update(request_id, "000000", "NOTE", {"note": "Please help"})
        assert create_response["statusCode"] == 403

    def test_post_update_missing_tracking_code(self):
        request_id, _ = _create_request()
        event = {
            "httpMethod": "POST",
            "path": f"/v1/citizen/rescue-requests/{request_id}/updates",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"updateType": "NOTE", "updatePayload": {"note": "Need help"}}),
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        response = create_update_handler(event, None)
        assert response["statusCode"] == 422

    def test_get_updates_not_found(self):
        list_response = _list_updates(str(uuid.uuid4()))
        assert list_response["statusCode"] == 404

    def test_get_updates_invalid_since(self):
        request_id, _ = _create_request()
        list_response = _list_updates(request_id, {"since": "not-a-datetime"})
        assert list_response["statusCode"] == 400

    def test_post_update_terminal_state_conflict(self):
        request_id, tracking_code = _create_request()
        cancel_event = {
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
                "reason": "No longer required",
            }),
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        cancel_response = cancel_handler(cancel_event, None)
        assert cancel_response["statusCode"] == 200

        create_response = _create_update(request_id, tracking_code, "NOTE", {"note": "Please help"})
        assert create_response["statusCode"] == 409
