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
os.environ["PRIORITIZATION_COMMANDS_TOPIC_ARN"] = ""
os.environ["PRIORITIZATION_REEVALUATE_TOPIC_ARN"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.handlers.internal.ingest_rescue_request_evaluations import handler as ingest_handler
from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.staff.get_current_state import handler as get_current_handler


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


def _create_request() -> tuple[str, str]:
    incident_id = str(uuid.uuid4())
    body = {
        "incidentId": incident_id,
        "requestType": "FLOOD",
        "description": "Priority evaluation integration test",
        "peopleCount": 2,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "contactName": "Priority Evaluation User",
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
    parsed = json.loads(response["body"])
    return parsed["requestId"], incident_id


class TestPrioritizationIngestFlow:
    def test_ingests_evaluated_event_and_updates_current_state(self):
        request_id, incident_id = _create_request()
        evaluation = {
            "header": {
                "messageType": "RescueRequestEvaluatedEvent",
                "messageId": str(uuid.uuid4()),
                "correlationId": str(uuid.uuid4()),
                "sentAt": "2026-04-17T00:05:00+00:00",
                "version": "1",
            },
            "body": {
                "requestId": request_id,
                "incidentId": incident_id,
                "evaluateId": str(uuid.uuid4()),
                "requestType": "FLOOD",
                "priorityScore": 0.91,
                "priorityLevel": "CRITICAL",
                "evaluateReason": "Children and bedridden residents need urgent rescue.",
                "lastEvaluatedAt": "2026-04-17T00:04:30+00:00",
                "description": "Need urgent evacuation",
                "location": {
                    "latitude": 13.7563,
                    "longitude": 100.5018,
                },
                "peopleCount": 2,
                "specialNeeds": ["bedridden", "children"],
            },
        }
        event = {
            "Records": [{
                "messageId": str(uuid.uuid4()),
                "body": json.dumps(evaluation),
                "messageAttributes": {},
            }]
        }

        result = ingest_handler(event, None)

        assert result == {"batchItemFailures": []}

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
        assert current["priorityScore"] == 0.91
        assert current["priorityLevel"] == "CRITICAL"
        assert current["latestPriorityEvaluationId"] == evaluation["body"]["evaluateId"]
        assert current["latestPriorityReason"] == evaluation["body"]["evaluateReason"]
