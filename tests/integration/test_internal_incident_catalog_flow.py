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

from src.handlers.internal.list_incident_catalog import handler as internal_list_handler


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


def test_internal_incident_catalog_returns_seeded_rows_with_internal_shape():
    event = {
        "httpMethod": "GET",
        "path": "/v1/internal/incidents/catalog",
        "headers": {},
        "body": None,
        "pathParameters": None,
        "queryStringParameters": None,
    }

    response = internal_list_handler(event, None)

    assert response["statusCode"] == 200
    result = json.loads(response["body"])
    assert "items" in result

    items = result["items"]
    mock_ids = {item["incident_id"] for item in items}
    assert {
        "f3e1c8b2-6a1d-4c22-a9f3-5f8b7a1d2e10",
        "9a0d7b34-2f6e-4b87-8d1a-3c7f5e2a9b44",
        "2c4f9e71-8b55-4d6a-b3a1-1e7f0c4d8a22",
        "7d2a1b5c-3e44-45f8-9c12-6b0e3f9d7a61",
        "c1b8e3d4-5f92-4a7c-8d6e-2f0a9b3c7d58",
    }.issubset(mock_ids)
    assert all(
        set(item.keys()) == {"incident_id", "incident_type", "incident_name", "status", "incident_description"}
        for item in items
    )
