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

from src.handlers.public.create_rescue_request import handler as create_handler


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


class TestIdempotencyFlow:
    def _build_event(self, body: dict, idempotency_key: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return {
            "httpMethod": "POST",
            "path": "/v1/rescue-requests",
            "headers": headers,
            "body": json.dumps(body),
            "pathParameters": None,
            "queryStringParameters": None,
        }

    def test_idempotent_create_same_key_same_payload(self):
        idem_key = str(uuid.uuid4())
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "FLOOD",
            "description": "Idempotency test",
            "peopleCount": 2,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Idem User",
            "contactPhone": _random_phone(),
            "sourceChannel": "WEB",
        }

        response1 = create_handler(self._build_event(body, idem_key), None)
        assert response1["statusCode"] == 201
        result1 = json.loads(response1["body"])

        response2 = create_handler(self._build_event(body, idem_key), None)
        assert response2["statusCode"] == 201
        result2 = json.loads(response2["body"])

        assert result1["requestId"] == result2["requestId"]

    def test_idempotent_create_same_key_different_payload_409(self):
        idem_key = str(uuid.uuid4())
        body1 = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "FLOOD",
            "description": "First payload",
            "peopleCount": 2,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "User",
            "contactPhone": _random_phone(),
            "sourceChannel": "WEB",
        }
        body2 = dict(body1)
        body2["description"] = "Different payload"

        response1 = create_handler(self._build_event(body1, idem_key), None)
        assert response1["statusCode"] == 201

        response2 = create_handler(self._build_event(body2, idem_key), None)
        assert response2["statusCode"] == 409
