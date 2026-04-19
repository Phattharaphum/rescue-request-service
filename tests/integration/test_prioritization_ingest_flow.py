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

from src.adapters.persistence.rescue_request_repository import get_current_state
from src.handlers.internal.ingest_rescue_request_evaluations import handler as ingest_handler
from src.handlers.public.create_citizen_update import handler as create_citizen_update_handler
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


def _create_request() -> tuple[str, str, str, str]:
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
    return parsed["requestId"], incident_id, parsed["trackingCode"], parsed["submittedAt"]


def _create_citizen_update(request_id: str, tracking_code: str) -> None:
    event = {
        "httpMethod": "POST",
        "path": f"/v1/citizen/rescue-requests/{request_id}/updates",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "trackingCode": tracking_code,
            "updateType": "PEOPLE_COUNT",
            "updatePayload": {"peopleCount": 4},
        }),
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": None,
    }
    response = create_citizen_update_handler(event, None)
    assert response["statusCode"] == 201


def _build_evaluated_message(
    *,
    request_id: str,
    incident_id: str,
    submitted_at: str | None,
    correlation_id: str,
    message_type: str = "RescueRequestEvaluatedEvent",
    evaluate_id: str | None = None,
) -> dict:
    body = {
        "requestId": request_id,
        "incidentId": incident_id,
        "evaluateId": evaluate_id or str(uuid.uuid4()),
        "requestType": "FLOOD",
        "priorityScore": 0.91,
        "priorityLevel": "CRITICAL",
        "evaluateReason": "Children and bedridden residents need urgent rescue.",
        "lastEvaluatedAt": "2026-04-18T00:04:30+00:00",
        "description": "Need urgent evacuation",
        "location": {
            "latitude": 13.7563,
            "longitude": 100.5018,
        },
        "peopleCount": 2,
        "specialNeeds": ["bedridden", "children"],
    }
    if submitted_at is not None:
        body["submittedAt"] = submitted_at

    return {
        "header": {
            "messageType": message_type,
            "messageId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "sentAt": "2026-04-18T00:05:00+00:00",
            "version": "1",
        },
        "body": body,
    }


def _build_sns_wrapped_sqs_event(topic_arn: str, message: dict, record_message_id: str | None = None) -> dict:
    notification = {
        "Type": "Notification",
        "MessageId": str(uuid.uuid4()),
        "TopicArn": topic_arn,
        "Timestamp": "2026-04-18T00:05:00+00:00",
        "MessageAttributes": {
            "messageType": {"Type": "String", "Value": message["header"]["messageType"]},
            "correlationId": {"Type": "String", "Value": message["header"]["correlationId"]},
            "version": {"Type": "String", "Value": message["header"]["version"]},
        },
        "Message": json.dumps(message),
    }
    return {
        "Records": [{
            "messageId": record_message_id or str(uuid.uuid4()),
            "body": json.dumps(notification),
            "messageAttributes": {},
        }]
    }


def _get_public_current_state(request_id: str) -> dict:
    get_event = {
        "httpMethod": "GET",
        "headers": {},
        "body": None,
        "pathParameters": {"requestId": request_id},
        "queryStringParameters": None,
    }
    current_response = get_current_handler(get_event, None)
    assert current_response["statusCode"] == 200
    return json.loads(current_response["body"])


class TestPrioritizationIngestFlow:
    def test_ingests_canonical_evaluated_event_from_created_topic(self):
        request_id, incident_id, _, submitted_at = _create_request()
        raw_current = get_current_state(request_id)
        correlation_id = raw_current["latestPrioritySourceEventId"]

        event = _build_sns_wrapped_sqs_event(
            topic_arn="arn:aws:sns:ap-southeast-1:000000000000:rescue-prioritization-created-v1-local",
            message=_build_evaluated_message(
                request_id=request_id,
                incident_id=incident_id,
                submitted_at=submitted_at,
                correlation_id=correlation_id,
            ),
        )

        result = ingest_handler(event, None)

        assert result == {"batchItemFailures": []}
        current = _get_public_current_state(request_id)
        assert current["priorityScore"] == 0.91
        assert current["priorityLevel"] == "CRITICAL"
        assert current["status"] == "TRIAGED"
        assert current["latestPriorityCorrelationId"] == correlation_id

    def test_accepts_legacy_re_evaluate_event_on_updated_topic(self):
        request_id, incident_id, tracking_code, submitted_at = _create_request()
        _create_citizen_update(request_id, tracking_code)
        raw_current = get_current_state(request_id)
        correlation_id = raw_current["latestPrioritySourceEventId"]

        event = _build_sns_wrapped_sqs_event(
            topic_arn="arn:aws:sns:ap-southeast-1:000000000000:rescue-prioritization-updated-v1-local",
            message=_build_evaluated_message(
                request_id=request_id,
                incident_id=incident_id,
                submitted_at=submitted_at,
                correlation_id=correlation_id,
                message_type="RescueRequestReEvaluateEvent",
            ),
        )

        result = ingest_handler(event, None)

        assert result == {"batchItemFailures": []}
        current = _get_public_current_state(request_id)
        assert current["status"] == "TRIAGED"
        assert current["latestPriorityCorrelationId"] == correlation_id
        assert current["latestPriorityReason"] == "Children and bedridden residents need urgent rescue."

    def test_rejects_stale_evaluation_from_old_source_event(self):
        request_id, incident_id, tracking_code, submitted_at = _create_request()
        initial_current = get_current_state(request_id)
        old_correlation_id = initial_current["latestPrioritySourceEventId"]

        _create_citizen_update(request_id, tracking_code)
        latest_current = get_current_state(request_id)
        assert latest_current["latestPrioritySourceEventId"] != old_correlation_id

        record_message_id = str(uuid.uuid4())
        event = _build_sns_wrapped_sqs_event(
            topic_arn="arn:aws:sns:ap-southeast-1:000000000000:rescue-prioritization-updated-v1-local",
            message=_build_evaluated_message(
                request_id=request_id,
                incident_id=incident_id,
                submitted_at=submitted_at,
                correlation_id=old_correlation_id,
            ),
            record_message_id=record_message_id,
        )

        result = ingest_handler(event, None)

        assert result == {"batchItemFailures": [{"itemIdentifier": record_message_id}]}
        current = _get_public_current_state(request_id)
        assert current["status"] == "SUBMITTED"
        assert current.get("latestPriorityEvaluationId") is None

    def test_accepts_event_without_submitted_at(self):
        request_id, incident_id, _, _ = _create_request()
        raw_current = get_current_state(request_id)
        correlation_id = raw_current["latestPrioritySourceEventId"]

        event = _build_sns_wrapped_sqs_event(
            topic_arn="arn:aws:sns:ap-southeast-1:000000000000:rescue-prioritization-created-v1-local",
            message=_build_evaluated_message(
                request_id=request_id,
                incident_id=incident_id,
                submitted_at=None,
                correlation_id=correlation_id,
            ),
        )

        result = ingest_handler(event, None)

        assert result == {"batchItemFailures": []}
        current = _get_public_current_state(request_id)
        assert current["status"] == "TRIAGED"
        assert current["latestPriorityCorrelationId"] == correlation_id
