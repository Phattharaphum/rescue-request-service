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

from src.adapters.persistence.rescue_request_repository import get_current_state, list_events
from src.handlers.internal.ingest_mission_status_changed import handler as ingest_handler
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
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "CatalogOrderIndex",
                    "KeySchema": [
                        {"AttributeName": "catalogPartition", "KeyType": "HASH"},
                        {"AttributeName": "catalogSortKey", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )


def _ensure_incident_in_catalog(incident_id: str) -> None:
    boto3.resource("dynamodb", endpoint_url="http://localhost:4566", region_name="ap-southeast-1").Table(
        "IncidentCatalogTable"
    ).put_item(
        Item={
            "incidentId": incident_id,
            "incidentType": "flood",
            "incidentName": "Mission Integration Incident",
            "status": "ACTIVE",
            "incidentDescription": "Seeded for mission status integration test",
        }
    )


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    try:
        _create_tables()
    except Exception:
        pytest.skip("LocalStack DynamoDB not available")


def _create_request() -> tuple[str, str]:
    incident_id = str(uuid.uuid4())
    _ensure_incident_in_catalog(incident_id)
    event = {
        "httpMethod": "POST",
        "path": "/v1/rescue-requests",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "incidentId": incident_id,
                "requestType": "EVACUATION",
                "description": "Mission status integration test",
                "peopleCount": 2,
                "latitude": 13.7563,
                "longitude": 100.5018,
                "contactName": "Mission Status User",
                "contactPhone": _random_phone(),
                "sourceChannel": "WEB",
            }
        ),
        "pathParameters": None,
        "queryStringParameters": None,
    }
    response = create_handler(event, None)
    assert response["statusCode"] == 201
    return json.loads(response["body"])["requestId"], incident_id


def _mission_status_sqs_event(
    *,
    request_id: str,
    incident_id: str,
    mission_id: str,
    new_status: str,
    changed_at: str,
    message_id: str | None = None,
) -> dict:
    return {
        "Records": [
            {
                "messageId": message_id or str(uuid.uuid4()),
                "body": json.dumps(
                    {
                        "schema_version": "1.0",
                        "mission_id": mission_id,
                        "requestId": request_id,
                        "incident_id": incident_id,
                        "rescue_team_id": "team-alpha",
                        "old_status": "ASSIGNED",
                        "new_status": new_status,
                        "changed_at": changed_at,
                        "changed_by": "team-alpha",
                    }
                ),
                "messageAttributes": {
                    "messageType": {"StringValue": "MissionStatusChanged"},
                    "correlationId": {"StringValue": mission_id},
                    "schemaVersion": {"StringValue": "1.0"},
                },
            }
        ]
    }


class TestMissionStatusIngestFlow:
    def test_ingests_en_route_and_resolved_statuses(self):
        request_id, incident_id = _create_request()
        mission_id = str(uuid.uuid4())

        en_route_result = ingest_handler(
            _mission_status_sqs_event(
                request_id=request_id,
                incident_id=incident_id,
                mission_id=mission_id,
                new_status="EN_ROUTE",
                changed_at="2026-04-29T00:04:00+00:00",
            ),
            None,
        )

        assert en_route_result == {"batchItemFailures": []}
        current = get_current_state(request_id)
        assert current["status"] == "IN_PROGRESS"
        assert current["latestMissionId"] == mission_id
        assert current["latestMissionStatus"] == "EN_ROUTE"
        assert current["latestMissionRescueTeamId"] == "team-alpha"
        assert current["latestMissionChangedBy"] == "team-alpha"
        assert current["assignedUnitId"] == "team-alpha"

        resolved_result = ingest_handler(
            _mission_status_sqs_event(
                request_id=request_id,
                incident_id=incident_id,
                mission_id=mission_id,
                new_status="RESOLVED",
                changed_at="2026-04-29T00:10:00+00:00",
            ),
            None,
        )

        assert resolved_result == {"batchItemFailures": []}
        current = get_current_state(request_id)
        assert current["status"] == "RESOLVED"
        assert current["latestMissionStatus"] == "RESOLVED"

        events = list_events(request_id, limit=10)["items"]
        assert [item["newStatus"] for item in events][-2:] == ["IN_PROGRESS", "RESOLVED"]
        assert events[-1]["missionId"] == mission_id
