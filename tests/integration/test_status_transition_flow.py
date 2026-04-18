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

from src.handlers.commands.assign import handler as assign_handler
from src.handlers.commands.cancel import handler as cancel_handler
from src.handlers.commands.resolve import handler as resolve_handler
from src.handlers.commands.start import handler as start_handler
from src.handlers.commands.triage import handler as triage_handler
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


def _create_request() -> str:
    body = {
        "incidentId": f"incident-{uuid.uuid4()}",
        "requestType": "FLOOD",
        "description": "Transition test",
        "peopleCount": 2,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "contactName": "Transition User",
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
    return json.loads(response["body"])["requestId"]


def _build_command_event(request_id: str, body: dict) -> dict:
    return {
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": None,
    }


class TestStatusTransitionFlow:
    def test_full_lifecycle(self):
        request_id = _create_request()

        # Triage
        response = triage_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
                "priorityScore": 0.85,
                "priorityLevel": "HIGH",
            }),
            None,
        )
        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert result["newStatus"] == "TRIAGED"

        # Assign
        response = assign_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
                "responderUnitId": "unit-alpha",
            }),
            None,
        )
        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert result["newStatus"] == "ASSIGNED"

        # Start
        response = start_handler(
            _build_command_event(request_id, {
                "changedBy": "unit-alpha",
                "changedByRole": "responder",
            }),
            None,
        )
        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert result["newStatus"] == "IN_PROGRESS"

        # Resolve
        response = resolve_handler(
            _build_command_event(request_id, {
                "changedBy": "unit-alpha",
                "changedByRole": "responder",
                "note": "All people rescued safely",
            }),
            None,
        )
        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert result["newStatus"] == "RESOLVED"

        # Verify current state
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
        assert current["status"] == "RESOLVED"
        assert current["stateVersion"] == 5

    def test_cancel_from_submitted(self):
        request_id = _create_request()

        response = cancel_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
                "reason": "Duplicate request",
            }),
            None,
        )
        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert result["newStatus"] == "CANCELLED"

    def test_assign_without_responder_unit_fails(self):
        request_id = _create_request()

        # Assign without responderUnitId
        response = assign_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
            }),
            None,
        )
        assert response["statusCode"] == 422

    def test_assign_from_submitted_succeeds(self):
        request_id = _create_request()

        response = assign_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
                "responderUnitId": "unit-direct",
                "priorityScore": 0.9,
                "priorityLevel": "CRITICAL",
            }),
            None,
        )
        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert result["previousStatus"] == "SUBMITTED"
        assert result["newStatus"] == "ASSIGNED"

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
        assert current["status"] == "ASSIGNED"
        assert current["assignedUnitId"] == "unit-direct"
        assert current["priorityScore"] == 0.9
        assert current["priorityLevel"] == "CRITICAL"

    def test_cancel_without_reason_fails(self):
        request_id = _create_request()

        response = cancel_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
            }),
            None,
        )
        assert response["statusCode"] == 422

    def test_invalid_transition_fails(self):
        request_id = _create_request()

        # Try to resolve directly from SUBMITTED
        response = resolve_handler(
            _build_command_event(request_id, {
                "changedBy": "staff-001",
                "changedByRole": "dispatcher",
            }),
            None,
        )
        assert response["statusCode"] == 409
