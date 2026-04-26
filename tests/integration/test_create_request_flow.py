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
os.environ["INCIDENT_CATALOG_TABLE_NAME"] = "IncidentCatalogTable"
os.environ["SNS_TOPIC_ARN"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.handlers.public.create_rescue_request import handler as create_handler
from src.handlers.staff.get_rescue_request import handler as get_handler


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
    dynamodb = boto3.resource("dynamodb", endpoint_url="http://localhost:4566", region_name="ap-southeast-1")
    dynamodb.Table("IncidentCatalogTable").put_item(Item={
        "incidentId": incident_id,
        "incidentType": "flood",
        "incidentName": "Integration Incident",
        "status": "ACTIVE",
        "incidentDescription": "Seeded for create request integration test",
    })


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    try:
        _create_tables()
    except Exception:
        pytest.skip("LocalStack DynamoDB not available")


class TestCreateRequestFlow:
    def _build_event(self, body: dict, headers: dict | None = None) -> dict:
        incident_id = body.get("incidentId")
        if isinstance(incident_id, str) and incident_id.strip():
            _ensure_incident_in_catalog(incident_id)
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
            "requestType": "EVACUATION",
            "description": "Test flood rescue",
            "peopleCount": 3,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Test User",
            "contactPhone": _random_phone(),
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

    def test_create_request_invalid_json_returns_standard_bad_request(self):
        event = {
            "httpMethod": "POST",
            "path": "/v1/rescue-requests",
            "headers": {"Content-Type": "application/json"},
            "body": "{invalid-json",
            "pathParameters": None,
            "queryStringParameters": None,
            "requestContext": {"requestId": "req-invalid-json"},
        }

        response = create_handler(event, None)

        assert response["statusCode"] == 400
        result = json.loads(response["body"])
        assert result["errorCode"] == "BAD_REQUEST"
        assert result["message"] == "Request body must be valid JSON"
        assert result["path"] == "/v1/rescue-requests"
        assert result["requestId"] == "req-invalid-json"
        assert response["headers"]["X-Trace-Id"] == result["traceId"]

    def test_create_and_get_request(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "MEDICAL",
            "description": "Fire rescue needed",
            "peopleCount": 2,
            "latitude": 13.8,
            "longitude": 100.6,
            "contactName": "Test User 2",
            "contactPhone": _random_phone(),
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
        assert get_result["updateItems"] == []

    def test_create_request_duplicate_phone_conflict(self):
        phone = _random_phone()
        body1 = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "EVACUATION",
            "description": "First request",
            "peopleCount": 2,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Dup User 1",
            "contactPhone": phone,
            "sourceChannel": "WEB",
        }
        body2 = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "MEDICAL",
            "description": "Second request with same phone",
            "peopleCount": 1,
            "latitude": 13.7001,
            "longitude": 100.5001,
            "contactName": "Dup User 2",
            "contactPhone": phone,
            "sourceChannel": "MOBILE",
        }

        response1 = create_handler(self._build_event(body1), None)
        assert response1["statusCode"] == 201
        response2 = create_handler(self._build_event(body2), None)
        assert response2["statusCode"] == 409

    def test_create_request_rejects_nan_coordinates(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "EVACUATION",
            "description": "NaN coordinate request",
            "peopleCount": 1,
            "latitude": float("nan"),
            "longitude": 100.5018,
            "contactName": "NaN User",
            "contactPhone": _random_phone(),
            "sourceChannel": "WEB",
        }
        response = create_handler(self._build_event(body), None)
        assert response["statusCode"] == 422

    def test_create_request_rejects_invalid_enums(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "NOT_A_REAL_TYPE",
            "description": "Invalid request type",
            "peopleCount": 1,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Enum User",
            "contactPhone": _random_phone(),
            "sourceChannel": "UNKNOWN",
        }
        response = create_handler(self._build_event(body), None)
        assert response["statusCode"] == 422

    def test_create_request_rejects_people_count_outside_dynamodb_limit(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "EVACUATION",
            "description": "Huge people count",
            "peopleCount": int("9" * 39),
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Huge Count User",
            "contactPhone": _random_phone(),
            "sourceChannel": "WEB",
        }
        response = create_handler(self._build_event(body), None)
        assert response["statusCode"] == 422

    def test_create_request_rejects_unknown_incident_id(self):
        body = {
            "incidentId": f"incident-{uuid.uuid4()}",
            "requestType": "EVACUATION",
            "description": "Unknown incident id",
            "peopleCount": 2,
            "latitude": 13.7563,
            "longitude": 100.5018,
            "contactName": "Unknown Incident User",
            "contactPhone": _random_phone(),
            "sourceChannel": "WEB",
        }
        response = create_handler(
            {
                "httpMethod": "POST",
                "path": "/v1/rescue-requests",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(body),
                "pathParameters": None,
                "queryStringParameters": None,
            },
            None,
        )
        assert response["statusCode"] == 422
        result = json.loads(response["body"])
        assert result["details"] == [
            {"field": "incidentId", "issue": "must reference an existing incident in IncidentCatalogTable"}
        ]
