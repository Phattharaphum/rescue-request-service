# Prioritization And Incident Sync

## Overview

This document describes the two new integrations added to the Rescue Request Service:

1. asynchronous prioritization with Rescue Prioritization Service
2. incident catalog synchronization from IncidentTracking Service

The implementation keeps the main rescue-request APIs independent from both integrations.
User-facing flows continue to read primarily from DynamoDB.

## What Was Added

### Prioritization integration

- Logical channel names still follow the async contract:
  - `rescue.prioritization.commands.v1`
  - `rescue.prioritization.updated.v1`
- AWS SNS physical topic names use hyphens because SNS topic names do not allow `.`:
- New SNS topic for initial prioritize requests:
  - `rescue-prioritization-commands-v1-{stage}`
- New SNS topic for re-evaluation requests:
  - `rescue-prioritization-updated-v1-{stage}`
- New SQS queue for evaluated results:
  - `rescue-prioritization-evaluated-{stage}`
- New DLQ for failed result ingestion:
  - `rescue-prioritization-evaluated-dlq-{stage}`
- New Lambda consumer:
  - `src.handlers.internal.ingest_rescue_request_evaluations.handler`

### Incident sync integration

- New DynamoDB table:
  - `IncidentCatalogTable-{stage}`
- New scheduled Lambda:
  - `src.handlers.internal.sync_incidents.handler`
- EventBridge schedule:
  - `rate(30 minutes)`
- Lambda timeout:
  - `30` seconds

## Runtime Flow

### 1. Initial prioritization

When `POST /v1/rescue-requests` succeeds:

- the rescue request is stored in DynamoDB
- the existing internal SNS event is still published
- a `RescueRequestPrioritizeCommand` is published on logical channel `rescue.prioritization.commands.v1`
- the backing AWS topic created by this stack is `rescue-prioritization-commands-v1-{stage}`
- the latest outbound prioritization message metadata is stored in `CURRENT_STATE`

### 2. Re-evaluation

When a request is updated in a way that can affect priority:

- `PATCH /v1/rescue-requests/{requestId}`
- citizen update types `PEOPLE_COUNT`, `SPECIAL_NEEDS`, `LOCATION_DETAILS`

the service publishes `RescueRequestReEvaluateEvent` on logical channel `rescue.prioritization.updated.v1` using the latest request snapshot.
The backing AWS topic created by this stack is `rescue-prioritization-updated-v1-{stage}`.

### 3. Evaluated score ingestion

When a `RescueRequestEvaluatedEvent` arrives through the SQS queue:

- the message is validated
- `evaluateId` is used as the idempotency key
- the service updates `CURRENT_STATE.priorityScore`
- the service updates `CURRENT_STATE.priorityLevel`
- the service stores evaluation metadata:
  - `latestPriorityEvaluationId`
  - `latestPriorityReason`
  - `latestPriorityEvaluatedAt`
  - `latestPriorityCorrelationId`
  - `lastPriorityIngestedAt`

If the request is already terminal (`RESOLVED` or `CANCELLED`), the message is acknowledged and skipped.

## Incident Catalog Flow

`SyncIncidentCatalogFunction` reads IncidentTracking Service through Secrets Manager configuration, then upserts records into `IncidentCatalogTable-{stage}`.

Stored business fields:

- `incidentId`
- `incidentType`
- `incidentName`
- `status`
- `incidentDescription`

Additional metadata stored for ordering and operations:

- `incidentSequence`
- `remoteCreatedAt`
- `remoteUpdatedAt`
- `lastSyncedAt`
- `catalogPartition`
- `catalogSortKey`

### Incident naming

The upstream API does not provide `incident_name`.

The service therefore generates stable names in running order:

- `IncidentA`
- `IncidentB`
- `IncidentC`
- ...
- `IncidentZ`
- `IncidentAA`

Existing incidents keep their original generated name on later syncs.

## API Usage

### List incidents for citizen/staff selection

Endpoint:

- `GET /v1/incidents`

Query parameters:

- `limit` optional, default `20`
- `cursor` optional
- `status` optional

Example response:

```json
{
  "items": [
    {
      "incidentId": "019C774D-1AC5-758B-AE95-5CD4AEB89258",
      "incidentType": "fire",
      "incidentName": "IncidentA",
      "incidentSequence": 1,
      "status": "REPORTED",
      "incidentDescription": "Fire reported near TU Dome (Verified)",
      "remoteCreatedAt": "2026-02-22T00:00:00Z",
      "remoteUpdatedAt": "2026-02-22T00:01:04Z",
      "lastSyncedAt": "2026-04-17T08:00:00+00:00"
    }
  ],
  "nextCursor": null
}
```

## Secrets Manager Configuration

The sync Lambda reads one secret from AWS Secrets Manager.

Secret name created by SAM:

- `rescue-request-service/incident-tracking/{stage}`

Expected JSON shape:

```json
{
  "apiUrl": "https://incident-service.krittamark.com/api/v1/incidents",
  "apiKey": "REPLACE_ME",
  "accept": "application/json",
  "transactionIdHeader": "X-IncidentTNX-Id"
}
```

Update the secret after deployment before expecting incident sync to succeed.

## Deployment Notes

### Outputs added by SAM

- `IncidentCatalogTableName`
- `RescuePrioritizationCommandsTopicArn`
- `RescuePrioritizationUpdatesTopicArn`
- `RescuePrioritizationEvaluatedQueueUrl`
- `RescuePrioritizationEvaluatedQueueArn`
- `IncidentTrackingApiSecretArn`

### Optional auto-subscription for evaluated events

`template.yaml` accepts parameter:

- `PrioritizationEvaluatedTopicArn`

If provided, the stack creates the SNS-to-SQS subscription automatically.
If omitted, the queue is still created and can be subscribed manually.

## Local Development

### 1. Create LocalStack DynamoDB tables

```powershell
make local-db-start
```

This now creates:

- `RescueRequestTable`
- `IdempotencyTable`
- `IncidentCatalogTable`

### 2. Create local SNS topics

```powershell
aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1
aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-prioritization-commands-v1
aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-prioritization-updated-v1
```

### 3. Create local Secrets Manager secret

```powershell
aws secretsmanager create-secret `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --name rescue-request-service/incident-tracking/local `
  --secret-string "{\"apiUrl\":\"https://incident-service.krittamark.com/api/v1/incidents\",\"apiKey\":\"123\",\"accept\":\"application/json\",\"transactionIdHeader\":\"X-IncidentTNX-Id\"}"
```

### 4. Start SAM local

```powershell
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

## Contract Note About Message #3

The source document is internally inconsistent for Message #3:

- the producer/consumer direction says it is sent from Rescue Request Service to Prioritization Service
- the example body looks like an already evaluated result

The implementation therefore treats `rescue.prioritization.updated.v1` as a re-evaluation trigger carrying the latest rescue-request snapshot.
This matches the producer/consumer direction and the described business purpose.

## Verification

The implementation was verified with:

- all unit tests passing
- integration smoke tests passing for:
  - create request
  - citizen status
  - list by incident
  - update priority
  - prioritization ingest
  - incident list
