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
from src.adapters.utils.masking import mask_phone
from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.public.get_citizen_status import handler as get_citizen_status_handler


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


def _random_phone() -> str:
    return "08" + str(uuid.uuid4().int % 10**8).zfill(8)


def _create_request() -> tuple[str, str]:
    phone = _random_phone()
    body = {
        "incidentId": f"incident-{uuid.uuid4()}",
        "requestType": "FLOOD",
        "description": "Citizen status details test",
        "peopleCount": 4,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "contactName": "Citizen Status User",
        "contactPhone": phone,
        "sourceChannel": "WEB",
        "locationDetails": "Near the school",
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
    return json.loads(response["body"])["requestId"], phone


class TestCitizenStatusFlow:
    def test_returns_detailed_tracking_snapshot(self):
        request_id, phone = _create_request()

        triage_event = {
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "changedBy": "dispatcher-01",
                "changedByRole": "dispatcher",
                "priorityScore": 0.75,
                "priorityLevel": "HIGH",
                "note": "Verified and forwarded",
                "meta": {"queue": "A1", "channel": "RADIO"},
            }),
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        triage_response = triage_handler(triage_event, None)
        assert triage_response["statusCode"] == 200

        get_event = {
            "httpMethod": "GET",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        response = get_citizen_status_handler(get_event, None)
        assert response["statusCode"] == 200
        result = json.loads(response["body"])

        assert result["requestId"] == request_id
        assert result["status"] == "TRIAGED"
        assert result["statusMessage"] is not None
        assert result["nextSuggestedAction"] is not None
        assert result["description"] == "Citizen status details test"
        assert result["peopleCount"] == 4
        assert result["contactPhoneMasked"] == mask_phone(phone)
        assert result["location"]["locationDetails"] == "Near the school"
        assert result["priorityLevel"] == "HIGH"
        assert result["latestNote"] == "Verified and forwarded"
        assert result["stateVersion"] == 2
        assert result["latestEvent"]["newStatus"] == "TRIAGED"
        assert result["latestEvent"]["meta"]["queue"] == "A1"
        assert len(result["recentEvents"]) >= 1
