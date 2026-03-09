import json
import os
import uuid

import boto3
import pytest

# Set environment before importing application code
os.environ["STAGE"] = "local"
os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:4566"
os.environ["AWS_REGION"] = "ap-southeast-1"
os.environ["DYNAMODB_TABLE_NAME"] = "RescueRequestTable"
os.environ["IDEMPOTENCY_TABLE_NAME"] = "IdempotencyTable"
os.environ["SNS_TOPIC_ARN"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.staff.get_rescue_request import handler as get_handler


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


class TestCreateRequestFlow:
    def _build_event(self, body: dict, headers: dict | None = None) -> dict:
        return {
            "httpMethod": "POST",
            "path": "/v1/rescue-requests",
            "headers": headers or {"Content-Type": "application/json"},
            "body": json.dumps(body),
            "pathParameters": None,
            "queryStringParameters": None,
        }

    def test_create_request_success(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "FLOOD",
            "description": "Test flood rescue",
            "peopleCount": 3,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Test User",
            "contactPhone": "0812345678",
            "sourceChannel": "WEB",
        }
        response = create_handler(self._build_event(body), None)
        assert response["statusCode"] == 201
        result = json.loads(response["body"])
        assert "requestId" in result
        assert "trackingCode" in result
        assert result["status"] == "SUBMITTED"
        assert len(result["trackingCode"]) == 6

    def test_create_request_missing_fields(self):
        body = {"description": "Incomplete request"}
        response = create_handler(self._build_event(body), None)
        assert response["statusCode"] == 422

    def test_create_and_get_request(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "FIRE",
            "description": "Fire rescue needed",
            "peopleCount": 2,
            "latitude": 13.8,
            "longitude": 100.6,
            "contactName": "Test User 2",
            "contactPhone": "0899999999",
            "sourceChannel": "MOBILE",
        }
        create_response = create_handler(self._build_event(body), None)
        assert create_response["statusCode"] == 201
        result = json.loads(create_response["body"])
        request_id = result["requestId"]

        get_event = {
            "httpMethod": "GET",
            "path": f"/v1/rescue-requests/{request_id}",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": {"includeEvents": "true"},
        }
        get_response = get_handler(get_event, None)
        assert get_response["statusCode"] == 200
        get_result = json.loads(get_response["body"])
        assert get_result["master"]["requestId"] == request_id
        assert get_result["currentState"]["status"] == "SUBMITTED"
