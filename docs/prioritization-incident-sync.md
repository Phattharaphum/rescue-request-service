# Prioritization Result Ingest And Incident Sync

## Overview

This document describes the two async integrations currently active in Rescue Request Service:

1. service-owned domain event publishing on `rescue-request-events-v1-{stage}`
2. inbound prioritization-result ingest plus incident catalog sync

The REST API remains database-first. Client reads do not call Prioritization Service or
IncidentTracking Service inline.

## Service-Owned Async Surface

### Topic

- `rescue-request-events-v1-{stage}`

This service publishes only its own rescue-request domain events to that SNS topic.
It does not create or own outbound prioritization command topics.

### Published Events

| Event Type | Trigger | Body Fields |
|------------|---------|-------------|
| `rescue-request.created` | New request created | `requestId`, `data` |
| `rescue-request.status-changed` | Any state transition | `requestId`, `previousStatus`, `newStatus`, `eventId`, `version` |
| `rescue-request.citizen-updated` | Citizen update or staff PATCH edit | Citizen update: `requestId`, `updateId`, `updateType`, `updatePayload`, `createdAt`; PATCH: `requestId`, `updateId="patch"`, `updateType="PATCH"`, `updatePayload` |
| `rescue-request.priority-score-updated` | Staff priority sync API updates score | `requestId`, `previousPriorityScore`, `newPriorityScore`, optional `priorityLevel`, optional `note`, optional `updatedAt` |
| `rescue-request.resolved` | Request resolved | `requestId`, `eventId` |
| `rescue-request.cancelled` | Request cancelled | `requestId`, `eventId`, `reason` |

### SNS Envelope

Published SNS messages use the current `header` + `body` envelope:

```json
{
  "header": {
    "messageId": "uuid",
    "eventType": "rescue-request.created",
    "schemaVersion": "1.0",
    "producer": "rescue-request-service",
    "occurredAt": "2026-04-18T00:00:00+00:00",
    "traceId": "uuid",
    "correlationId": "uuid",
    "partitionKey": "request-id",
    "contentType": "application/json"
  },
  "body": {}
}
```

### Internal Stream Relay

The internal `/stream` relay may normalize or repackage events for SSE delivery.
That relay shape is internal-only and should not be treated as a public contract.

### Message Attributes

The owner topic publishes these SNS message attributes for subscription filters:

| Attribute | Value |
|-----------|-------|
| `eventType` | e.g. `rescue-request.created` |
| `schemaVersion` | `1.0` |
| `producer` | `rescue-request-service` |

### Non-Blocking Publish

Event publishing is non-blocking. A publish failure is logged but does not fail the HTTP request.

## Prioritization Result Ingest

### Ownership Boundary

This service no longer publishes outbound prioritization command or re-evaluation topics.
Instead, it consumes evaluated results produced externally by Rescue Prioritization Service.

### Inbound Topics And Queue

One shared SQS queue is used for prioritization results:

- queue: `rescue-prioritization-evaluated-{stage}`
- DLQ: `rescue-prioritization-evaluated-dlq-{stage}`

That queue can subscribe to two external SNS topics:

- `rescue.prioritization.created.v1`
- `rescue.prioritization.updated.v1`

`template.yaml` and `template.local.yaml` expose optional parameters:

- `PrioritizationCreatedTopicArn`
- `PrioritizationUpdatedTopicArn`

If either ARN is provided, the stack creates the SNS-to-SQS subscription automatically.
If omitted, the queue still exists and can be subscribed manually.

### Canonical Inbound Contract

Canonical inbound `messageType` on both topics is:

- `RescueRequestEvaluatedEvent`

Canonical payload:

```json
{
  "header": {
    "messageType": "RescueRequestEvaluatedEvent",
    "correlationId": "uuid",
    "sentAt": "2026-04-18T00:05:00+00:00",
    "version": "1"
  },
  "body": {
    "requestId": "REQ-8812-4444",
    "incidentId": "8b9b6d5b-7d5e-4d0b-a7e2-2a0a6bd5c111",
    "evaluateId": "b26c6606-c16f-4f25-bb4c-3cd1c9f7005f",
    "requestType": "flood_rescue",
    "priorityScore": 0.3,
    "priorityLevel": "NORMAL",
    "evaluateReason": "Lack of food reserves indicates a potential need for assistance.",
    "submittedAt": "2026-03-03T08:01:12Z",
    "lastEvaluatedAt": "2026-03-22T07:18:39.670351+00:00",
    "description": "ไม่มีอาหารสํารอง",
    "location": {
      "latitude": 11.111,
      "longitude": 11.222
    },
    "peopleCount": 1,
    "specialNeeds": ["bedridden", "children"]
  }
}
```

### Compatibility Rule

For transition compatibility only, the consumer also accepts:

- `messageType = RescueRequestReEvaluateEvent`

but only when the inbound topic/channel is `rescue.prioritization.updated.v1`.
Documentation treats `RescueRequestEvaluatedEvent` as the steady-state contract.

### Validation Rules

Inbound result messages must satisfy:

- `header.sentAt` is ISO-8601
- `header.version` equals `1`
- `header.correlationId` is present
- `body.requestId` is present
- `body.incidentId` is a valid UUID
- `body.evaluateId` is a valid UUID
- `body.requestType` is present
- `body.priorityScore` is a decimal between `0` and `1`
- `body.priorityLevel` is one of `LOW`, `NORMAL`, `HIGH`, `CRITICAL`
- `body.evaluateReason` is present
- `body.submittedAt`, when present, is ISO-8601
- `body.lastEvaluatedAt` is ISO-8601
- `body.description` is present
- `body.peopleCount` is a positive integer
- `body.location` exists and contains valid numeric `latitude` and `longitude`
- `body.specialNeeds`, when present, is an array of non-empty strings

### Correlation Rule

`header.correlationId` must match the latest service-owned source event stored on the request:

- `CURRENT_STATE.latestPrioritySourceEventId`

That source event comes from the service-owned topic:

- `rescue-request.created`
- `rescue-request.citizen-updated`

This prevents stale prioritization results from overwriting newer request context.

### State Updates On Successful Ingest

When a result is accepted, the service updates `CURRENT_STATE` with:

- `priorityScore`
- `priorityLevel`
- `latestPriorityEvaluationId`
- `latestPriorityReason`
- `latestPriorityEvaluatedAt`
- `latestPriorityCorrelationId`
- `lastPriorityIngestedAt`
- `lastUpdatedAt`
- `lastUpdatedBy = "prioritization-service"`

Status handling:

- `SUBMITTED -> TRIAGED`
- later non-terminal statuses are preserved
- terminal requests are acknowledged and skipped

Idempotency remains keyed by:

- `RescueRequestEvaluatedEvent#{evaluateId}`

## Incident Catalog Sync

### Resources

- DynamoDB table: `IncidentCatalogTable-{stage}`
- Lambda: `src.handlers.internal.sync_incidents.handler`
- EventBridge schedule: `rate(30 minutes)`
- Lambda timeout: `30` seconds

### Secret Configuration

Secret name:

- `rescue-request-service/incident-tracking/{stage}`

Expected JSON:

```json
{
  "apiUrl": "https://incident-service.krittamark.com/api/v1/incidents",
  "apiKey": "REPLACE_ME",
  "accept": "application/json",
  "transactionIdHeader": "X-IncidentTNX-Id"
}
```

Required keys:

- `apiUrl`
- `apiKey`

Optional keys:

- `accept`
- `transactionIdHeader`

### Stored Fields

Business fields stored in `IncidentCatalogTable`:

- `incidentId`
- `incidentType`
- `incidentName`
- `status`
- `incidentDescription`

Operational fields also stored:

- `incidentSequence`
- `remoteCreatedAt`
- `remoteUpdatedAt`
- `lastSyncedAt`
- `catalogPartition`
- `catalogSortKey`

### Incident Naming

Upstream does not provide `incident_name`, so this service generates stable running names:

- `IncidentA`
- `IncidentB`
- `IncidentC`
- ...

### Read Path

`GET /v1/incidents` reads from `IncidentCatalogTable` only.
Temporary upstream timeouts or sync failures do not block client reads.

## Deployment Notes

Relevant outputs:

- `IncidentCatalogTableName`
- `RescuePrioritizationEvaluatedQueueUrl`
- `RescuePrioritizationEvaluatedQueueArn`
- `IncidentTrackingApiSecretArn`

## Local Development

### Local DynamoDB

```powershell
make local-db-start
```

This prepares:

- `RescueRequestTable`
- `IdempotencyTable`
- `IncidentCatalogTable`

### Local SNS Topics

Only the service-owned topic must be created by this service locally:

```powershell
aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1
```

If you want to exercise prioritization-result ingest end to end, create the external topics separately:

```powershell
aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-prioritization-created-v1
aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-prioritization-updated-v1
```

### Local Secret

```powershell
aws secretsmanager create-secret `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --name rescue-request-service/incident-tracking/local `
  --secret-string "{\"apiUrl\":\"https://incident-service.krittamark.com/api/v1/incidents\",\"apiKey\":\"123\",\"accept\":\"application/json\",\"transactionIdHeader\":\"X-IncidentTNX-Id\"}"
```

### SAM Local

```powershell
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

`template.local.yaml` now includes SQS event mapping for `IngestPrioritizationEvaluationsFunction`
to mirror deploy behavior, so queue-driven ingest wiring is aligned between local and deploy templates.
