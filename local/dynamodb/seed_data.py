"""Seed sample data into local DynamoDB tables for development."""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import boto3

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:4566")
REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
TABLE_NAME = "RescueRequestTable"


def get_table():
    dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT, region_name=REGION)
    return dynamodb.Table(TABLE_NAME)


def seed():
    table = get_table()
    now = datetime.now(timezone.utc).isoformat()
    request_id = "sample-request-001"
    incident_id = "incident-flood-2024-001"

    # Master
    table.put_item(Item={
        "PK": f"REQ#{request_id}",
        "SK": "META",
        "itemType": "MASTER",
        "requestId": request_id,
        "incidentId": incident_id,
        "requestType": "FLOOD",
        "description": "Water level rising rapidly, need evacuation",
        "peopleCount": 5,
        "latitude": Decimal("13.7563"),
        "longitude": Decimal("100.5018"),
        "contactName": "Sample User",
        "contactPhone": "0812345678",
        "contactPhoneNormalized": "0812345678",
        "contactPhoneHash": "sample_phone_hash",
        "trackingCodeHash": "sample_tracking_hash",
        "sourceChannel": "WEB",
        "submittedAt": now,
    })

    # Current State
    table.put_item(Item={
        "PK": f"REQ#{request_id}",
        "SK": "CURRENT",
        "itemType": "CURRENT_STATE",
        "requestId": request_id,
        "incidentId": incident_id,
        "lastEventId": "sample-event-001",
        "stateVersion": 1,
        "status": "SUBMITTED",
        "lastUpdatedBy": "system",
        "lastUpdatedAt": now,
    })

    # Initial Event
    table.put_item(Item={
        "PK": f"REQ#{request_id}",
        "SK": "EVENT#0000000001",
        "itemType": "STATUS_EVENT",
        "eventId": "sample-event-001",
        "requestId": request_id,
        "previousStatus": None,
        "newStatus": "SUBMITTED",
        "changedBy": "system",
        "changedByRole": "system",
        "changeReason": "Initial submission",
        "version": 1,
        "occurredAt": now,
    })

    # Tracking Lookup
    table.put_item(Item={
        "PK": "TRACK#sample_phone_hash",
        "SK": "CODE#sample_tracking_hash",
        "itemType": "TRACKING_LOOKUP",
        "phoneHash": "sample_phone_hash",
        "trackingCodeHash": "sample_tracking_hash",
        "requestId": request_id,
        "incidentId": incident_id,
        "createdAt": now,
    })

    # Incident Projection
    table.put_item(Item={
        "PK": f"INCIDENT#{incident_id}",
        "SK": f"REQUEST#{now}#{request_id}",
        "itemType": "INCIDENT_PROJECTION",
        "requestId": request_id,
        "incidentId": incident_id,
        "status": "SUBMITTED",
        "requestType": "FLOOD",
        "submittedAt": now,
    })

    print(f"Seeded sample data for request: {request_id}")


if __name__ == "__main__":
    seed()
