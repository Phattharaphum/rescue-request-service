# Data Model

## Overview

The service currently uses 3 DynamoDB tables:

1. `RescueRequestTable-{stage}` for the main rescue-request domain model
2. `IdempotencyTable-{stage}` for idempotent write coordination and replay
3. `RescueRequestStreamEventLog-{stage}` for the internal stream relay only

`RescueRequestStreamEventLog-{stage}` and the `/stream` Lambda are internal implementation
details for the first-party frontend. Systems that need subscription or pub/sub delivery
should subscribe to SNS directly, or create their own SQS subscription.

## 1. RescueRequestTable

Single-table design with composite primary key:

- Partition key: `PK` (String)
- Sort key: `SK` (String)

### Item Types

| Item Type | PK | SK | Purpose |
|-----------|----|----|---------|
| `MASTER` | `REQ#{requestId}` | `META` | Original rescue request submitted by the citizen |
| `CURRENT_STATE` | `REQ#{requestId}` | `CURRENT` | Latest lifecycle snapshot used by staff/citizen views |
| `STATUS_EVENT` | `REQ#{requestId}` | `EVENT#{version:010d}` | Append-only status transition history |
| `CITIZEN_UPDATE` | `REQ#{requestId}` | `UPDATE#{createdAt}#{updateId}` | Additional information submitted by the citizen |
| `TRACKING_LOOKUP` | `TRACK#{phoneHash}` | `CODE#{trackingCodeHash}` | Lookup index for phone + tracking code |
| `PHONE_UNIQUE` | `PHONE#{phoneHash}` | `UNIQUE` | Enforces one active request per normalized phone hash |
| `INCIDENT_PROJECTION` | `INCIDENT#{incidentId}` | `REQUEST#{submittedAt}#{requestId}` | Incident-level query projection |
| `DUPLICATE_SIGNATURE` | `DUP#{signature}` | `REQUEST#{requestId}` | Duplicate-detection window entry |

### Access Patterns

| Access Pattern | Key / Query |
|----------------|-------------|
| Get master record by request ID | `PK=REQ#{requestId}`, `SK=META` |
| Get current state by request ID | `PK=REQ#{requestId}`, `SK=CURRENT` |
| List status events | `PK=REQ#{requestId}`, `SK begins_with EVENT#` |
| List citizen updates | `PK=REQ#{requestId}`, `SK begins_with UPDATE#` |
| Tracking-code lookup | `PK=TRACK#{phoneHash}`, `SK=CODE#{trackingCodeHash}` |
| Check phone uniqueness | query `PK=TRACK#{phoneHash}` or read `PHONE#{phoneHash}` uniqueness item |
| List requests by incident | `PK=INCIDENT#{incidentId}`, `SK begins_with REQUEST#` |
| Check duplicate within time bucket | query `PK=DUP#{signature}` |

### Shared Notes

- Numeric values may be stored as DynamoDB `Number` and converted back to Python `int`/`float` in the repository layer.
- Fields with `None` values are omitted from writes to `RescueRequestTable`.
- `append_event_and_update_current(...)` writes the `STATUS_EVENT` and updates `CURRENT_STATE` together.

### Entity Fields

#### `MASTER`

- `itemType`
- `requestId`
- `incidentId`
- `requestType`
- `description`
- `peopleCount`
- `specialNeeds`
- `latitude`
- `longitude`
- `locationDetails`
- `province`
- `district`
- `subdistrict`
- `addressLine`
- `contactName`
- `contactPhone`
- `contactPhoneNormalized`
- `contactPhoneHash`
- `trackingCodeHash`
- `sourceChannel`
- `submittedAt`
- `lastCitizenUpdateAt`

#### `CURRENT_STATE`

- `itemType`
- `requestId`
- `incidentId`
- `lastEventId`
- `stateVersion`
- `status`
- `priorityScore`
- `priorityLevel`
- `assignedUnitId`
- `assignedAt`
- `latestNote`
- `lastUpdatedBy`
- `lastUpdatedAt`

#### `STATUS_EVENT`

- `itemType`
- `eventId`
- `requestId`
- `previousStatus`
- `newStatus`
- `changedBy`
- `changedByRole`
- `changeReason`
- `meta`
- `priorityScore`
- `responderUnitId`
- `version`
- `occurredAt`

Notes:

- `changeReason` is populated from request body field `reason` in the current implementation.
- The initial submission also creates version `1` as a `STATUS_EVENT`.

#### `CITIZEN_UPDATE`

- `itemType`
- `updateId`
- `requestId`
- `updateType`
- `updatePayload`
- `citizenAuthMethod`
- `citizenPhoneHash`
- `trackingCodeHash`
- `clientIp`
- `userAgent`
- `createdAt`

#### `TRACKING_LOOKUP`

- `itemType`
- `phoneHash`
- `trackingCodeHash`
- `requestId`
- `incidentId`
- `createdAt`

#### `PHONE_UNIQUE`

- `itemType`
- `phoneHash`
- `requestId`
- `createdAt`

#### `INCIDENT_PROJECTION`

- `itemType`
- `requestId`
- `incidentId`
- `status`
- `requestType`
- `contactName`
- `submittedAt`

#### `DUPLICATE_SIGNATURE`

- `itemType`
- `requestId`
- `signature`
- `createdAt`

## 2. IdempotencyTable

Primary key:

- Partition key: `idempotencyKeyHash` (String)

Purpose:

- Reserve a key before mutating work starts
- Replay the stored response for completed requests
- Detect key reuse with a different request fingerprint
- Track failed operations and lock expiry

### Fields

- `idempotencyKeyHash`
- `operationName`
- `requestFingerprint`
- `status`
- `lockOwner`
- `lockedAt`
- `lockExpiresAt`
- `createdAt`
- `updatedAt`
- `expiresAt`
- `clientId`
- `requestIp`
- `userAgent`
- `responseStatusCode`
- `responseBody`
- `resultResourceId`
- `errorCode`
- `errorMessage`

### Status Values

- `IN_PROGRESS`
- `COMPLETED`
- `FAILED`

### Notes

- TTL uses `expiresAt` and is currently set to 24 hours from reservation time.
- In-progress locks use `lockExpiresAt` and currently reserve a 5-minute processing window.
- Response replay uses the stored `responseStatusCode` and `responseBody`.

## 3. RescueRequestStreamEventLog

This table backs the internal SSE relay only.

Primary key:

- Partition key: `streamKey` (String)
- Sort key: `eventKey` (String)

TTL:

- `expiresAt`

### Item Types

| Item Type | streamKey | eventKey | Purpose |
|-----------|-----------|----------|---------|
| Stream event | `STREAM` (default) | `{timestampMs}#{eventId}` | Event persisted for SSE polling |
| Poller lease | `LOCK` | `POLLER` | Cooperative lease so only one poller actively drains SQS |

### Stream Event Fields

- `streamKey`
- `eventKey`
- `payload`
- `createdAt`
- `expiresAt`

### Poller Lease Fields

- `streamKey`
- `eventKey`
- `leaseOwner`
- `leaseExpiresAt`
- `updatedAt`

### Notes

- Events are consumed from the SNS-backed SQS queue and copied into this table by `stream-service/src/poller.mjs`.
- The current poller stores an internal normalized `payload` object for SSE consumption.
- Event retention is currently 86400 seconds (24 hours).
