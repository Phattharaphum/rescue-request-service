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
    assert {"MOCK-INC-001", "MOCK-INC-002", "MOCK-INC-003", "MOCK-INC-004", "MOCK-INC-005"}.issubset(mock_ids)
    assert all(
        set(item.keys()) == {"incident_id", "incident_type", "incident_name", "status", "incident_description"}
        for item in items
    )
