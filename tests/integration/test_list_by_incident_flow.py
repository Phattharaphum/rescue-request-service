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
os.environ["SNS_TOPIC_ARN"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.handlers.commands.triage import handler as triage_handler
from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.staff.list_by_incident import handler as list_by_incident_handler


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


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    try:
        _create_tables()
    except Exception:
        pytest.skip("LocalStack DynamoDB not available")


def _create_request(incident_id: str, contact_phone: str) -> str:
    body = {
        "incidentId": incident_id,
        "requestType": "FLOOD",
        "description": "Need evacuation support",
        "peopleCount": 3,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "contactName": "Incident List Test",
        "contactPhone": contact_phone,
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


def _triage_request(request_id: str) -> None:
    event = {
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "changedBy": "dispatcher-01",
            "changedByRole": "dispatcher",
            "priorityScore": 0.75,
            "priorityLevel": "HIGH",
            "note": "Verified and forwarded",
        }),
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": None,
    }
    response = triage_handler(event, None)
    assert response["statusCode"] == 200


def _list_by_incident(incident_id: str, status: str | None = None) -> dict:
    query = {"status": status} if status else None
    event = {
        "httpMethod": "GET",
        "headers": {},
        "body": None,
        "pathParameters": {"incidentId": incident_id},
        "queryStringParameters": query,
    }
    response = list_by_incident_handler(event, None)
    assert response["statusCode"] == 200
    return json.loads(response["body"])


class TestListByIncidentFlow:
    def test_returns_latest_status_and_full_details(self):
        incident_id = f"incident-{uuid.uuid4()}"
        triaged_phone = _random_phone()
        submitted_phone = _random_phone()
        triaged_id = _create_request(incident_id, triaged_phone)
        submitted_id = _create_request(incident_id, submitted_phone)
        _triage_request(triaged_id)

        result = _list_by_incident(incident_id)
        by_id = {item["requestId"]: item for item in result["items"]}

        triaged_item = by_id[triaged_id]
        assert triaged_item["status"] == "TRIAGED"
        assert triaged_item["description"] == "Need evacuation support"
        assert triaged_item["contactPhone"] == triaged_phone
        assert triaged_item["currentState"]["status"] == "TRIAGED"
        assert triaged_item["currentState"]["priorityLevel"] == "HIGH"

        submitted_item = by_id[submitted_id]
        assert submitted_item["status"] == "SUBMITTED"
        assert submitted_item["currentState"]["status"] == "SUBMITTED"

    def test_status_filter_uses_latest_state(self):
        incident_id = f"incident-{uuid.uuid4()}"
        triaged_id = _create_request(incident_id, _random_phone())
        _create_request(incident_id, _random_phone())
        _triage_request(triaged_id)

        result = _list_by_incident(incident_id, status="TRIAGED")
        returned_ids = {item["requestId"] for item in result["items"]}
        assert returned_ids == {triaged_id}
