# Asynchronous Function Contract (Code-Verified)

Last verified against source code: 2026-05-16

This document is the contract for asynchronous behavior implemented by this service.
It is derived from deployed infrastructure (`template.yaml`) and runtime code under `src/` and `stream-service/`.

## 1) Scope

Included:
- Inbound asynchronous consumers:
- `IngestPrioritizationEvaluationsFunction` (SQS)
- `IngestMissionStatusChangedFunction` (SQS)
- Scheduled asynchronous workers:
- `SyncIncidentCatalogFunction` (EventBridge schedule)
- `StreamPollerFunction` (EventBridge schedule)
- Stream delivery function URL:
- `StreamSseFunction` (`/stream`)
- Outbound asynchronous SNS events published by this service.

Excluded:
- API Gateway synchronous HTTP contracts (`/v1/...`) covered in `docs/SynchronousFunctionContract.md`.

## 2) Deployed Async Functions

| Function | Trigger | Key runtime config | Handler |
|---|---|---|---|
| `IngestPrioritizationEvaluationsFunction` | SQS `rescue-prioritization-evaluated-{stage}` | BatchSize `5`, `ReportBatchItemFailures`, queue visibility `60s`, DLQ maxReceiveCount `3` | `src.handlers.internal.ingest_rescue_request_evaluations.handler` |
| `IngestMissionStatusChangedFunction` | SQS `rescue-mission-status-changed-{stage}` | BatchSize `5`, `ReportBatchItemFailures`, queue visibility `60s`, DLQ maxReceiveCount `3` | `src.handlers.internal.ingest_mission_status_changed.handler` |
| `SyncIncidentCatalogFunction` | EventBridge schedule | `rate(30 minutes)`, timeout `30s` | `src.handlers.internal.sync_incidents.handler` |
| `StreamPollerFunction` | EventBridge schedule | `rate(1 minute)`, timeout `60s` | `stream-service/src/poller.mjs` |
| `StreamSseFunction` | Lambda Function URL | Auth `NONE`, invoke mode `RESPONSE_STREAM`, timeout `900s` | `stream-service/src/stream.mjs` |

## 3) Async Infrastructure Topology

### 3.1 Outbound event topic
- Topic: `rescue-request-events-v1-{stage}`
- Producer: this service.

### 3.2 Stream fan-out path
- SNS topic -> SQS queue `rescue-request-events-v1-stream-{stage}` -> `StreamPollerFunction` -> DynamoDB `RescueRequestStreamEventLog-{stage}` -> `StreamSseFunction`.

### 3.3 Prioritization ingest path
- Queue: `rescue-prioritization-evaluated-{stage}`
- DLQ: `rescue-prioritization-evaluated-dlq-{stage}`
- Optional auto-subscriptions controlled by parameters:
- `PrioritizationCreatedTopicArn`
- `PrioritizationUpdatedTopicArn`
- Queue policy also allows matching source ARN patterns for:
- `rescue-prioritization-created-v1*`
- `rescue-prioritization-updated-v1*`

### 3.4 Mission status ingest path
- Queue: `rescue-mission-status-changed-{stage}`
- DLQ: `rescue-mission-status-changed-dlq-{stage}`
- Optional auto-subscription controlled by parameter:
- `MissionStatusChangedTopicArn`
- Queue policy allows source ARN pattern `mission-status-changed-v1*`.

## 4) Outbound SNS Contract

## 4.1 Publish transport behavior

Publisher implementation: `src/adapters/messaging/sns_publisher.py`.

Message transport:
- `Message` is JSON envelope (see section 4.2).
- `MessageAttributes` currently include only:
- `eventType`
- `schemaVersion` (`1.0`)
- `producer`

Important runtime behavior:
- If `SNS_TOPIC_ARN` is configured, message is published to SNS.
- If `SNS_TOPIC_ARN` is empty, publish is skipped and warning is logged.
- In both cases, publisher still returns a generated envelope header object to caller.

## 4.2 Outbound envelope shape

```json
{
  "header": {
    "messageId": "uuid",
    "eventType": "string",
    "schemaVersion": "1.0",
    "producer": "rescue-request-service",
    "occurredAt": "ISO-8601",
    "traceId": "uuid",
    "correlationId": "uuid-or-caller-supplied",
    "partitionKey": "requestId",
    "contentType": "application/json"
  },
  "body": {}
}
```

Header rules:
- `messageId` generated per event.
- `traceId` generated unless explicitly supplied.
- `correlationId` generated unless explicitly supplied.
- `partitionKey` is always the `requestId` passed by caller.

## 4.3 Published event types

### Event: `rescue-request.created`
Trigger:
- `POST /v1/rescue-requests` successful create flow.

Body shape:

```json
{
  "requestId": "uuid",
  "data": {
    "...": "full request master snapshot"
  }
}
```

Correlation behavior:
- Explicitly set to `requestId` in create flow.

### Event: `rescue-request.citizen-updated`
Triggers:
- `POST /v1/citizen/rescue-requests/{requestId}/updates`
- `PATCH /v1/rescue-requests/{requestId}`

Body base fields:

```json
{
  "requestId": "uuid",
  "updateId": "uuid-or-patch",
  "updateType": "NOTE|LOCATION_DETAILS|PEOPLE_COUNT|SPECIAL_NEEDS|CONTACT_INFO|PATCH"
}
```

Optional body fields by trigger:
- `incidentId` (present in both create-citizen-update and patch flows)
- `updatePayload` (present when source flow provides changed payload)
- `createdAt` (present in create-citizen-update flow)

Correlation behavior:
- No explicit correlation passed by these flows (auto-generated UUID).

### Event: `rescue-request.status-changed`
Triggers:
- Command endpoints (`triage/assign/start/resolve/cancel`)
- `POST /v1/rescue-requests/{requestId}/events`
- Prioritization ingest updates
- Mission status ingest mapped transitions

Body shape:

```json
{
  "requestId": "uuid",
  "previousStatus": "SUBMITTED|TRIAGED|ASSIGNED|IN_PROGRESS|RESOLVED|CANCELLED",
  "newStatus": "SUBMITTED|TRIAGED|ASSIGNED|IN_PROGRESS|RESOLVED|CANCELLED",
  "eventId": "uuid",
  "version": 2
}
```

Correlation behavior by source:
- Command handlers: auto-generated UUID.
- `append_status_event` use case: explicit `correlationId=requestId`.
- Prioritization ingest: forwarded inbound `header.correlationId`.
- Mission ingest: `header.correlationId` or `header.messageId` or `missionId` fallback.

### Event: `rescue-request.resolved`
Triggers:
- Resolve command flow.
- `append_status_event` when `newStatus=RESOLVED`.
- Mission ingest when mapped target is `RESOLVED`.

Body shape:

```json
{
  "requestId": "uuid",
  "eventId": "uuid"
}
```

### Event: `rescue-request.cancelled`
Triggers:
- Cancel command flow.
- `append_status_event` when `newStatus=CANCELLED`.

Body shape:

```json
{
  "requestId": "uuid",
  "eventId": "uuid",
  "reason": "string"
}
```

### Event: `rescue-request.priority-score-updated`
Trigger:
- `PATCH /v1/rescue-requests/{requestId}/priority` only when `priorityScore` is present in request body and score value actually changed.

Body shape:

```json
{
  "requestId": "uuid",
  "previousPriorityScore": 0.6,
  "newPriorityScore": 0.9,
  "priorityLevel": "string|null",
  "note": "string|null",
  "updatedAt": "ISO-8601"
}
```

Correlation behavior:
- Explicitly set to `requestId` in this flow.

## 5) Inbound SQS Contract: Prioritization Evaluations

Function:
- `IngestPrioritizationEvaluationsFunction`
- Handler: `src.handlers.internal.ingest_rescue_request_evaluations.handler`

Queue mapping behavior:
- Batch size `5`.
- Uses `ReportBatchItemFailures` response mode.
- Returns `{ "batchItemFailures": [{ "itemIdentifier": "..." }] }` for failed records only.

## 5.1 Supported incoming payload wrappers

Parser: `src/adapters/messaging/prioritization_parser.py`.

Accepted record body forms:
- SNS Notification wrapper with `Message` string.
- Direct envelope object with `header` + `body`.
- Raw object payload (wrapped by parser into `{header, body}`).

When SNS-wrapped:
- Header fields extracted from SNS metadata:
- `messageId`, `messageType`, `correlationId`, `sentAt`, `version`, `topicArn`, inferred `channel`.
- If inner `Message` already has `header/body`, parser merges SNS header + inner header (inner header wins on key overlap).

Channel inference from topic ARN:
- `rescue-prioritization-created-v1` -> `rescue.prioritization.created.v1`
- `rescue-prioritization-updated-v1` -> `rescue.prioritization.updated.v1`
- `rescue-prioritization-events-v1` -> `rescue.prioritization.events.v1`

## 5.2 Normalization rules before validation

Use case: `src/application/usecases/ingest_rescue_request_evaluation.py`.

Normalization:
- `header.messageType` may be mapped from `header.eventType`:
- `rescue.prioritization.evaluated.v1` -> `RescueRequestEvaluatedEvent`
- Legacy canonical alias normalized:
- `RescueRequestEvaluateEvent` -> `RescueRequestEvaluatedEvent`
- `body.evaluateId` fallback order:
- `evaluateId` -> `evaluationId` -> `header.messageId`
- `body.evaluateReason` fallback: `evaluateReason` -> `reason`
- `body.lastEvaluatedAt` fallback: `lastEvaluatedAt` -> `evaluatedAt`
- `specialNeeds` normalization:
- list stays list
- JSON list string parsed when possible
- comma-separated string split into trimmed list
- other types passed through as-is

## 5.3 Validation rules

Header validation:
- `header.messageType` must be:
- `RescueRequestEvaluatedEvent`, or
- `RescueRequestReEvaluateEvent` only when `channel` is `rescue.prioritization.updated.v1` or `rescue.prioritization.events.v1` (or topic ARN hint matches these channels)
- `header.sentAt` required ISO-8601
- `header.version` must be `1` or `1.0`
- `header.correlationId` required non-empty

Body validation:
- `requestId` required non-empty string
- `incidentId` valid UUID
- `evaluateId` valid UUID
- `requestType` one of `MEDICAL|EVACUATION|SUPPLY`
- `priorityScore` finite number in `[0,1]`
- `priorityLevel` one of `LOW|NORMAL|HIGH|CRITICAL`
- `evaluateReason` required non-empty string
- `description` required non-empty string
- `peopleCount` required positive integer
- `submittedAt` optional, if present must be ISO-8601
- `lastEvaluatedAt` required ISO-8601
- `location` required object with numeric `latitude` and `longitude`

Additional state validation:
- `requestId` must exist in current-state store.
- `header.correlationId` must exactly equal `CURRENT.latestPrioritySourceEventId`.

## 5.4 Processing behavior

Idempotency:
- key: `RescueRequestEvaluatedEvent#{evaluateId}`
- operation scope: `IngestRescueRequestEvaluatedEvent` + `SQS:/rescue-prioritization-evaluated/{requestId}`

Replay:
- returns result `{ "status": "duplicate", ... }`, record treated successful.

Terminal requests:
- returns `{ "status": "skipped_terminal", ... }`, record treated successful.

Non-terminal updates:
- Always appends a new `STATUS_EVENT` and increments `stateVersion`.
- Status resolution rule:
- If current status is `SUBMITTED`, new status becomes `TRIAGED`.
- Otherwise, status remains unchanged (event may be same-status transition, for example `TRIAGED -> TRIAGED`).
- Updates current state priority fields and provenance fields (`latestPriorityEvaluationId`, reason, timestamps, correlation tracking, etc.).
- Publishes `rescue-request.status-changed` (best effort; publish failure is logged and swallowed).

On validation/runtime exception per record:
- Record is added to `batchItemFailures` for retry.

## 6) Inbound SQS Contract: Mission Status Changed

Function:
- `IngestMissionStatusChangedFunction`
- Handler: `src.handlers.internal.ingest_mission_status_changed.handler`

Queue mapping behavior:
- Batch size `5`.
- Uses `ReportBatchItemFailures`.
- Returns per-record failures via `batchItemFailures`.

## 6.1 Supported incoming payload wrappers

Parser: `src/adapters/messaging/mission_status_parser.py`.

Accepted forms:
- SNS Notification wrapper.
- Direct envelope (`header/body`).
- Raw object payload.

When SNS-wrapped:
- Parser extracts header fields from SNS and infers `channel`.
- For topic ARN containing `mission-status-changed-v1` or `rescue-mission-status-changed`, inferred channel is `mission.status.changed.v1`.

## 6.2 Normalization rules before validation

Use case: `src/application/usecases/ingest_mission_status_changed.py`.

Normalization supports snake/camel/Pascal variants:
- `mission_id | missionId | MissionID` -> `missionId`
- `requestId | request_id | RequestID` -> `requestId`
- `incident_id | incidentId | IncidentID` -> `incidentId`
- `rescue_team_id | rescueTeamId | RescueTeamID` -> `rescueTeamId`
- `old_status | oldStatus | OldStatus` -> `oldStatus`
- `new_status | newStatus | NewStatus` -> `newStatus`
- `changed_at | changedAt | ChangedAt` -> `changedAt`
- `changed_by | changedBy | ChangedBy` -> `changedBy`
- `schema_version | schemaVersion` -> `schemaVersion` (fallback to header version)

## 6.3 Validation rules

Header/body rules:
- If `header.messageType` or `header.eventType` is present, value must be one of:
- `MissionStatusChanged`
- `MissionStatusChangedEvent`
- `mission.status.changed`
- `mission.status.changed.v1`
- If message type is absent, it is accepted.
- `body.schemaVersion` must be `1` or `1.0`.

Required body fields:
- `requestId`, `incidentId`, `missionId`, `rescueTeamId`, `newStatus`, `changedAt`, `changedBy`

Status and time constraints:
- `newStatus` must be one of `EN_ROUTE|ON_SITE|RESOLVED|NEED_BACKUP`
- `changedAt` must be ISO-8601

Additional state validation:
- `requestId` must exist.
- `incidentId` must match current state's `incidentId` when current value exists.

## 6.4 Processing behavior

Idempotency:
- key: `MissionStatusChangedEvent#{requestId}#{missionId}#{newStatus}#{changedAt}`
- operation scope: `IngestMissionStatusChangedEvent` + `SQS:/mission-status-changed/{requestId}`

Replay:
- returns `{ "status": "duplicate", ... }`, record successful.

Terminal requests:
- returns `{ "status": "skipped_terminal", ... }`, record successful.

Mission-to-request status mapping:
- `EN_ROUTE` -> `IN_PROGRESS`
- `RESOLVED` -> `RESOLVED`
- `ON_SITE`, `NEED_BACKUP` -> metadata only (no request lifecycle change)

Result modes:
- `metadata_updated_unmapped_status`: metadata update only.
- `metadata_updated_status_unchanged`: mapped status equals current request status; metadata update only.
- `updated`: mapped status transition applied; event appended and `stateVersion` incremented.

When transition is applied (`updated`):
- Appends `STATUS_EVENT` with mission metadata.
- Updates current state mission tracking fields.
- Sets `assignedUnitId=rescueTeamId`; sets `assignedAt=changedAt` only if currently unset.
- Publishes `rescue-request.status-changed`.
- Publishes `rescue-request.resolved` additionally when mapped target is `RESOLVED`.

On validation/runtime exception per record:
- Record is added to `batchItemFailures` for retry.

## 7) Scheduled Contract: Incident Catalog Sync

Function:
- `SyncIncidentCatalogFunction`
- Handler: `src.handlers.internal.sync_incidents.handler`
- Trigger: `rate(30 minutes)`

## 7.1 External dependency contract

Client: `src/adapters/external/incident_tracking_client.py`.

Required env config:
- `INCIDENT_SYNC_API_URL`
- `INCIDENT_SYNC_API_KEY`

Optional env config:
- `INCIDENT_SYNC_ACCEPT` (default `application/json`)
- `INCIDENT_SYNC_TRANSACTION_ID_HEADER` (default `X-IncidentTNX-Id`)
- `INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS` (default `30`)

Outgoing request:
- Method `GET`
- Headers:
- `Accept: <INCIDENT_SYNC_ACCEPT>`
- `api-key: <INCIDENT_SYNC_API_KEY>`
- `<INCIDENT_SYNC_TRANSACTION_ID_HEADER>: <generated-uuid>`

Expected response:
- JSON array of objects.
- Non-object rows are dropped.
- Non-array response or invalid JSON raises `ServiceUnavailableError`.

## 7.2 Upsert behavior

Use case: `src/application/usecases/sync_incident_catalog.py`.

Per fetched row:
- Requires non-empty `incident_id`; otherwise row is skipped.
- Existing incident keeps existing `incidentName` and sequence.
- New incident gets next sequence and generated name `IncidentA`, `IncidentB`, ... `IncidentZ`, `IncidentAA`, ...
- Upsert fields:
- `incidentId`, `incidentType`, `incidentName`, `incidentSequence`, `status`, `incidentDescription`
- `remoteCreatedAt`, `remoteUpdatedAt`, `lastSyncedAt`
- `catalogPartition="CATALOG"`
- `catalogSortKey="{sequence:06d}#{incidentId}"`

Return summary shape:

```json
{
  "fetched": 0,
  "created": 0,
  "updated": 0,
  "skipped": 0,
  "syncedAt": "ISO-8601"
}
```

## 8) Stream Subsystem Contract

## 8.1 Stream Poller (`StreamPollerFunction`)

Trigger:
- `rate(1 minute)` schedule.

Required env:
- `SNS_STREAM_SQS_QUEUE_URL`
- `STREAM_TABLE_NAME`

Defaults:
- `STREAM_KEY=STREAM`
- `POLLER_LOCK_KEY=POLLER`
- `POLLER_LEASE_MS=55000`
- `EVENT_RETENTION_SECONDS=86400`

Processing contract:
- Acquires lease in stream table key `{streamKey:"LOCK", eventKey:POLLER_LOCK_KEY}`.
- If lease unavailable, exits with:

```json
{ "processed": 0, "skipped": true, "reason": "lease-unavailable", "elapsedMs": 0 }
```

- If lease acquired:
- Long-polls SQS (`WaitTimeSeconds=20`, `MaxNumberOfMessages=10`, `VisibilityTimeout=30`).
- Persists each message payload into `STREAM_TABLE_NAME` then deletes SQS message.
- Item shape stored:
- `streamKey=STREAM_KEY`
- `eventKey=<13-digit timestamp>#<eventId>`
- `payload=<normalized event>`
- `createdAt`, `expiresAt`

Normalization behavior (`normalizeEvent`):
- If payload already has top-level `metadata` and `body`, keep as-is.
- Otherwise wraps into fallback:

```json
{
  "metadata": {
    "eventType": "rescue-request.unknown",
    "eventId": "generated-uuid",
    "timestamp": "ISO-8601",
    "partitionKey": "stream-fallback",
    "schemaVersion": "1.0",
    "source": "rescue-request-stream-poller",
    "correlationId": null
  },
  "body": "original-payload"
}
```

Note:
- Outbound SNS envelope from this service is `header/body` (not `metadata/body`), so stream poller currently stores it via fallback wrapper unless upstream payload already matches `metadata/body`.

## 8.2 SSE Stream (`StreamSseFunction` + Function URL)

Function URL:
- Auth `NONE`
- Path expected: `/stream`

Request handling:
- `OPTIONS /stream` -> `200` with CORS headers.
- Non-GET and non-OPTIONS -> `405` JSON `{ "message": "Method not allowed" }`.
- Wrong path -> `404` JSON `{ "message": "Not found" }`.
- Missing `STREAM_TABLE_NAME` -> `500` JSON.

SSE response (`GET /stream`):
- `Content-Type: text/event-stream; charset=utf-8`
- Emits:
- event chunks: `data: <json payload>\n\n`
- heartbeat comments: `: heartbeat\n\n`

Polling behavior:
- Starts cursor at current time (`{nowMs}#`), so it streams only events newer than connection start.
- Query condition: `eventKey > cursor`, ascending, limit 50 per poll.
- Poll interval default `1000ms`.
- Heartbeat interval default `15000ms`.
- Stream closes automatically near Lambda timeout.

CORS behavior:
- Allowed origin reflection for configured list (`ALLOWED_ORIGINS`), default first configured origin fallback.

## 9) Async Retry and Failure Semantics

SQS consumers:
- Both ingest functions use partial-batch failure reporting.
- Failed records are retried by Lambda SQS integration.
- After max receives (`3`), records move to respective DLQ.

Scheduled functions:
- No custom retry policy is declared in this template for schedule-triggered functions.

Outbound publish failures:
- Most caller flows treat publish as best effort (exceptions are caught/logged; main flow typically continues).

## 10) Known Current-Behavior Notes

- Prioritization ingest can append a status event with unchanged status (`previousStatus == newStatus`) for non-`SUBMITTED` requests.
- Mission ingest does not enforce domain transition matrix; it uses explicit mission-status mapping rules.
- Stream poller fallback schema (`metadata/body`) does not match service SNS envelope (`header/body`) and wraps such payloads as `rescue-request.unknown` events.
- No synchronous publish acknowledgement API is exposed externally for SNS publishes.

