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

from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.staff.get_current_state import handler as get_current_handler
from src.handlers.staff.update_rescue_request_priority import handler as update_priority_handler


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
        "incidentDescription": "Seeded for update priority integration test",
    })


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    try:
        _create_tables()
    except Exception:
        pytest.skip("LocalStack DynamoDB not available")


def _create_request() -> str:
    incident_id = f"incident-{uuid.uuid4()}"
    _ensure_incident_in_catalog(incident_id)
    body = {
        "incidentId": incident_id,
        "requestType": "EVACUATION",
        "description": "Priority update integration test",
        "peopleCount": 3,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "contactName": "Priority Flow",
        "contactPhone": _random_phone(),
        "sourceChannel": "WEB",
    }
    event = {
        "httpMethod": "POST",
        "path": "/v1/rescue-requests",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
        "pathParameters": None,
        "queryStringParameters": None,
    }
    response = create_handler(event, None)
    assert response["statusCode"] == 201
    return json.loads(response["body"])["requestId"]


def _update_priority(request_id: str, body: dict, headers: dict | None = None) -> dict:
    event = {
        "httpMethod": "PATCH",
        "headers": {"Content-Type": "application/json", **(headers or {})},
        "body": json.dumps(body),
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": None,
    }
    return update_priority_handler(event, None)


class TestUpdatePriorityFlow:
    def test_updates_current_priority_fields(self):
        request_id = _create_request()

        patch_response = _update_priority(
            request_id,
            {
                "priorityScore": 0.915,
                "priorityLevel": "CRITICAL",
                "note": "Escalated after reassessment",
            },
        )
        assert patch_response["statusCode"] == 200
        patch_result = json.loads(patch_response["body"])
        assert patch_result["requestId"] == request_id
        assert patch_result["priorityScore"] == 0.915
        assert patch_result["priorityLevel"] == "CRITICAL"
        assert patch_result["note"] == "Escalated after reassessment"
        assert patch_result["updated"] == ["priorityScore", "priorityLevel", "note"]

        get_event = {
            "httpMethod": "GET",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        current_response = get_current_handler(get_event, None)
        assert current_response["statusCode"] == 200
        current = json.loads(current_response["body"])
        assert current["priorityScore"] == 0.915
        assert current["priorityLevel"] == "CRITICAL"
        assert current["latestNote"] == "Escalated after reassessment"

    def test_if_match_mismatch_returns_conflict(self):
        request_id = _create_request()
        response = _update_priority(
            request_id=request_id,
            body={"priorityScore": 0.75},
            headers={"If-Match": "999"},
        )
        assert response["statusCode"] == 409

    def test_invalid_if_match_returns_standard_bad_request(self):
        request_id = _create_request()
        response = _update_priority(
            request_id=request_id,
            body={"priorityScore": 0.75},
            headers={"If-Match": "abc"},
        )

        assert response["statusCode"] == 400
        result = json.loads(response["body"])
        assert result["errorCode"] == "BAD_REQUEST"
        assert result["details"] == [{"field": "If-Match", "issue": "must be a valid integer"}]
