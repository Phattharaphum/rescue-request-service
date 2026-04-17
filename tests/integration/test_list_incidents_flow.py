import json
import os

import boto3
import pytest

os.environ["STAGE"] = "local"
os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:4566"
os.environ["AWS_REGION"] = "ap-southeast-1"
os.environ["INCIDENT_CATALOG_TABLE_NAME"] = "IncidentCatalogTable"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

from src.adapters.persistence.incident_catalog_repository import upsert_incident
from src.handlers.public.list_incidents import handler as list_incidents_handler


def _create_tables():
    dynamodb = boto3.client("dynamodb", endpoint_url="http://localhost:4566", region_name="ap-southeast-1")
    tables = dynamodb.list_tables()["TableNames"]

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


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    try:
        _create_tables()
    except Exception:
        pytest.skip("LocalStack DynamoDB not available")


class TestListIncidentsFlow:
    def test_lists_incidents_from_catalog_table(self):
        upsert_incident({
            "incidentId": "INC-001",
            "incidentType": "fire",
            "incidentName": "IncidentA",
            "incidentSequence": 1,
            "status": "REPORTED",
            "incidentDescription": "Fire near campus",
            "catalogPartition": "CATALOG",
            "catalogSortKey": "000001#INC-001",
        })
        upsert_incident({
            "incidentId": "INC-002",
            "incidentType": "flood",
            "incidentName": "IncidentB",
            "incidentSequence": 2,
            "status": "ACTIVE",
            "incidentDescription": "Flooded road",
            "catalogPartition": "CATALOG",
            "catalogSortKey": "000002#INC-002",
        })

        event = {
            "httpMethod": "GET",
            "path": "/v1/incidents",
            "headers": {},
            "body": None,
            "pathParameters": None,
            "queryStringParameters": None,
        }
        response = list_incidents_handler(event, None)

        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        names = [item["incidentName"] for item in result["items"]]
        assert "IncidentA" in names
        assert "IncidentB" in names

    def test_filters_incidents_by_status(self):
        event = {
            "httpMethod": "GET",
            "path": "/v1/incidents",
            "headers": {},
            "body": None,
            "pathParameters": None,
            "queryStringParameters": {"status": "ACTIVE"},
        }
        response = list_incidents_handler(event, None)

        assert response["statusCode"] == 200
        result = json.loads(response["body"])
        assert all(item["status"] == "ACTIVE" for item in result["items"])
