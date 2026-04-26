import json
import os
import uuid

import boto3
import pytest

os.environ["STAGE"] = "local"
os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:4566"
os.environ["AWS_REGION"] = "ap-southeast-1"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-1"
os.environ["DYNAMODB_TABLE_NAME"] = "RescueRequestTable"
os.environ["IDEMPOTENCY_TABLE_NAME"] = "IdempotencyTable"
os.environ["INCIDENT_CATALOG_TABLE_NAME"] = "IncidentCatalogTable"
os.environ["SNS_TOPIC_ARN"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.commands.cancel import handler as cancel_handler
from src.handlers.commands.triage import handler as triage_handler
from src.handlers.staff.get_current_state import handler as get_current_state_handler
from src.handlers.staff.get_rescue_request import handler as get_rescue_request_handler
from src.handlers.staff.patch_rescue_request import handler as patch_handler


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


def _new_seeded_incident_id() -> str:
    incident_id = f"incident-{uuid.uuid4()}"
    boto3.resource("dynamodb", endpoint_url="http://localhost:4566", region_name="ap-southeast-1").Table(
        "IncidentCatalogTable"
    ).put_item(Item={
        "incidentId": incident_id,
        "incidentType": "flood",
        "incidentName": "Integration Incident",
        "status": "ACTIVE",
        "incidentDescription": "Seeded for idempotency integration test",
    })
    return incident_id


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

    def _create_request(self, description: str = "Idempotency request") -> str:
        body = {
            "incidentId": _new_seeded_incident_id(),
            "requestType": "EVACUATION",
            "description": description,
            "peopleCount": 2,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Idem User",
            "contactPhone": _random_phone(),
            "sourceChannel": "WEB",
        }
        response = create_handler(self._build_event(body), None)
        assert response["statusCode"] == 201
        return json.loads(response["body"])["requestId"]

    def test_idempotent_create_same_key_same_payload(self):
        idem_key = str(uuid.uuid4())
        body = {
            "incidentId": _new_seeded_incident_id(),
            "requestType": "EVACUATION",
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
            "incidentId": _new_seeded_incident_id(),
            "requestType": "EVACUATION",
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

    def test_same_key_across_endpoints_is_scoped(self):
        request_id = self._create_request("Cross endpoint scope check")
        idem_key = str(uuid.uuid4())
        command_body = {
            "changedBy": "staff-001",
            "changedByRole": "dispatcher",
            "reason": "duplicate submission",
        }

        triage_event = {
            "httpMethod": "POST",
            "path": f"/v1/rescue-requests/{request_id}/triage",
            "headers": {"Content-Type": "application/json", "X-Idempotency-Key": idem_key},
            "body": json.dumps(command_body),
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        cancel_event = {
            "httpMethod": "POST",
            "path": f"/v1/rescue-requests/{request_id}/cancel",
            "headers": {"Content-Type": "application/json", "X-Idempotency-Key": idem_key},
            "body": json.dumps(command_body),
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }

        triage_response = triage_handler(triage_event, None)
        assert triage_response["statusCode"] == 200
        triage_result = json.loads(triage_response["body"])
        assert triage_result["newStatus"] == "TRIAGED"

        cancel_response = cancel_handler(cancel_event, None)
        assert cancel_response["statusCode"] == 200
        cancel_result = json.loads(cancel_response["body"])
        assert cancel_result["newStatus"] == "CANCELLED"
        assert cancel_result["eventId"] != triage_result["eventId"]

        current_event = {
            "httpMethod": "GET",
            "path": f"/v1/rescue-requests/{request_id}/current",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id},
            "queryStringParameters": None,
        }
        current_response = get_current_state_handler(current_event, None)
        assert current_response["statusCode"] == 200
        current = json.loads(current_response["body"])
        assert current["status"] == "CANCELLED"

    def test_same_key_across_resources_is_scoped(self):
        request_id_1 = self._create_request("Scope test request 1")
        request_id_2 = self._create_request("Scope test request 2")
        idem_key = str(uuid.uuid4())
        patch_body = {"description": "patched with shared idempotency key"}

        patch_event_1 = {
            "httpMethod": "PATCH",
            "path": f"/v1/rescue-requests/{request_id_1}",
            "headers": {"Content-Type": "application/json", "X-Idempotency-Key": idem_key},
            "body": json.dumps(patch_body),
            "pathParameters": {"requestId": request_id_1},
            "queryStringParameters": None,
        }
        patch_event_2 = {
            "httpMethod": "PATCH",
            "path": f"/v1/rescue-requests/{request_id_2}",
            "headers": {"Content-Type": "application/json", "X-Idempotency-Key": idem_key},
            "body": json.dumps(patch_body),
            "pathParameters": {"requestId": request_id_2},
            "queryStringParameters": None,
        }

        patch_response_1 = patch_handler(patch_event_1, None)
        assert patch_response_1["statusCode"] == 200
        patch_result_1 = json.loads(patch_response_1["body"])
        assert patch_result_1["requestId"] == request_id_1

        patch_response_2 = patch_handler(patch_event_2, None)
        assert patch_response_2["statusCode"] == 200
        patch_result_2 = json.loads(patch_response_2["body"])
        assert patch_result_2["requestId"] == request_id_2

        get_event_1 = {
            "httpMethod": "GET",
            "path": f"/v1/rescue-requests/{request_id_1}",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id_1},
            "queryStringParameters": None,
        }
        get_event_2 = {
            "httpMethod": "GET",
            "path": f"/v1/rescue-requests/{request_id_2}",
            "headers": {},
            "body": None,
            "pathParameters": {"requestId": request_id_2},
            "queryStringParameters": None,
        }

        get_response_1 = get_rescue_request_handler(get_event_1, None)
        assert get_response_1["statusCode"] == 200
        get_response_2 = get_rescue_request_handler(get_event_2, None)
        assert get_response_2["statusCode"] == 200

        result_1 = json.loads(get_response_1["body"])
        result_2 = json.loads(get_response_2["body"])
        assert result_1["master"]["description"] == "patched with shared idempotency key"
        assert result_2["master"]["description"] == "patched with shared idempotency key"
