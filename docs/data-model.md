# Data Model

## DynamoDB Tables

### Table 1: RescueRequestTable

Single-table design with composite primary key.

| Item Type | PK | SK | Description |
|-----------|----|----|-------------|
| Master | REQ#{requestId} | META | Request master data |
| Current State | REQ#{requestId} | CURRENT | Current state snapshot |
| Status Event | REQ#{requestId} | EVENT#{version:010d} | Status change events |
| Citizen Update | REQ#{requestId} | UPDATE#{createdAt}#{updateId} | Citizen updates |
| Tracking Lookup | TRACK#{phoneHash} | CODE#{trackingCodeHash} | Phone+tracking lookup |
| Incident Projection | INCIDENT#{incidentId} | REQUEST#{submittedAt}#{requestId} | Incident query |
| Duplicate Signature | DUP#{signature} | REQUEST#{requestId} | Duplicate detection |

### Table 2: IdempotencyTable

| Field | Type | Description |
|-------|------|-------------|
| idempotencyKeyHash | String (PK) | SHA-256 hash of idempotency key |
| operationName | String | Operation that was executed |
| requestFingerprint | String | Hash of request body |
| status | String | IN_PROGRESS, COMPLETED, FAILED |
| responseStatusCode | Number | HTTP status of stored response |
| responseBody | String | JSON body of stored response |
| expiresAt | Number | TTL epoch (24 hours) |

## Entity Fields

### Rescue Request Master
- requestId, incidentId, requestType, description
- peopleCount, specialNeeds
- latitude, longitude, locationDetails
- province, district, subdistrict, addressLine
- contactName, contactPhone, contactPhoneNormalized
- contactPhoneHash, trackingCodeHash
- sourceChannel, submittedAt, lastCitizenUpdateAt

### Current State
- requestId, incidentId, lastEventId, stateVersion
- status, priorityScore, priorityLevel
- assignedUnitId, assignedAt
- latestNote, lastUpdatedBy, lastUpdatedAt

### Status Event
- eventId, requestId, previousStatus, newStatus
- changedBy, changedByRole, changeReason
- meta, priorityScore, responderUnitId
- version, occurredAt

### Citizen Update
- updateId, requestId, updateType, updatePayload
- citizenAuthMethod, citizenPhoneHash, trackingCodeHash
- clientIp, userAgent, createdAt
