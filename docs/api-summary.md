# API Reference

**Base URL:** `Not available`

A machine-readable OpenAPI 3.0 specification is available at [`docs/openapi.yaml`](openapi.yaml).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Common Headers](#2-common-headers)
3. [Pagination](#3-pagination)
4. [Error Responses](#4-error-responses)
5. [Enumerations](#5-enumerations)
6. [Public Endpoints (Citizens)](#6-public-endpoints-citizens)
   - [GET /health, /health/live, /health/ready](#60-get-health-healthlive-healthready)
   - [POST /rescue-requests](#61-post-rescue-requests)
   - [POST /citizen/tracking/lookup](#62-post-citizentrackingLookup)
   - [GET /citizen/rescue-requests/{requestId}/status](#63-get-citizenrescue-requestsrequestidstatus)
   - [POST /citizen/rescue-requests/{requestId}/updates](#64-post-citizenrescue-requestsrequestidupdates)
   - [GET /citizen/rescue-requests/{requestId}/updates](#65-get-citizenrescue-requestsrequestidupdates)
   - [GET /incidents](#66-get-incidents)
7. [Staff Endpoints](#7-staff-endpoints)
   - [GET /rescue-requests/{requestId}](#71-get-rescue-requestsrequestid)
   - [PATCH /rescue-requests/{requestId}](#72-patch-rescue-requestsrequestid)
   - [GET /rescue-requests/{requestId}/events](#73-get-rescue-requestsrequestidevents)
   - [POST /rescue-requests/{requestId}/events](#74-post-rescue-requestsrequestidevents)
   - [GET /rescue-requests/{requestId}/current](#75-get-rescue-requestsrequestidcurrent)
   - [GET /incidents/{incidentId}/rescue-requests](#76-get-incidentsincidentidrescue-requests)
   - [GET /idempotency-keys/{idempotencyKeyHash}](#77-get-idempotency-keysidempotencykeyhash)
   - [PATCH /rescue-requests/{requestId}/priority](#78-patch-rescue-requestsrequestidpriority)
8. [Command Endpoints (State Machine)](#8-command-endpoints-state-machine)
   - [POST /rescue-requests/{requestId}/triage](#81-post-rescue-requestsrequestidtriage)
   - [POST /rescue-requests/{requestId}/assign](#82-post-rescue-requestsrequestidassign)
   - [POST /rescue-requests/{requestId}/start](#83-post-rescue-requestsrequestidstart)
   - [POST /rescue-requests/{requestId}/resolve](#84-post-rescue-requestsrequestidresolve)
   - [POST /rescue-requests/{requestId}/cancel](#85-post-rescue-requestsrequestidcancel)
9. [State Machine](#9-state-machine)
10. [Async Contract](#10-async-contract)
11. [Async Integrations](#11-async-integrations)
12. [Idempotency](#12-idempotency)
13. [Duplicate Detection](#13-duplicate-detection)
14. [Internal Endpoints](#14-internal-endpoints)
   - [GET /internal/incidents/catalog](#141-get-internalincidentscatalog)

---

## 1. Overview

The Rescue Request Service provides a REST API for managing disaster rescue requests.
It also exposes a local incident catalog for request creation. That catalog is refreshed
asynchronously from IncidentTracking Service every 30 minutes, while the API itself reads
from the service database snapshot.

| API Group | Audience | Auth Required |
|-----------|----------|---------------|
| **Public** | Citizens | No |
| **Staff** | Emergency-response staff | No (prepared for future) |
| **Commands** | Staff — state-machine transitions | No (prepared for future) |
| **Internal** | Internal operations/support tooling | No (network-restricted usage expected) |

---

## 2. Common Headers

| Header | Direction | Description |
|--------|-----------|-------------|
| `X-Idempotency-Key` | Request | UUID v4. Makes mutating operations safe to retry. Optional on all mutating endpoints. |
| `If-Match` | Request | Current `stateVersion` integer. Enforced on `POST /rescue-requests/{requestId}/events`, command endpoints, and `PATCH /rescue-requests/{requestId}/priority`. `PATCH /rescue-requests/{requestId}` currently accepts the header but does not enforce version checks. |
| `X-Forwarded-For` | Request | Client IP, set automatically by API Gateway. |
| `User-Agent` | Request | Client user-agent string. |
| `X-Trace-Id` | Response | Trace identifier included in every response. On error responses it matches `traceId` in the JSON body. |
| `Access-Control-Allow-Origin` | Response | Reflected when the request `Origin` is one of: `https://rescue-request.phatphum.me`, `http://localhost:3000` |
| `Vary` | Response | Always `Origin` on application responses |

---

## 3. Pagination

List endpoints use **cursor-based pagination**.

| Query Parameter | Type | Default | Range |
|----------------|------|---------|-------|
| `limit` | integer | 20 | 1 – 100 |
| `cursor` | string | — | Opaque base64 token from previous `nextCursor` |

All paginated responses follow this envelope:

```json
{
  "items": [ ... ],
  "nextCursor": "eyJQSyI6..."
}
```

`nextCursor` is `null` when there are no more pages.

---

## 4. Error Responses

All errors share the same JSON structure:

```json
{
  "message": "Human-readable description",
  "errorCode": "BAD_REQUEST",
  "traceId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "requestId": "3c85c0c5-4c2e-4c6a-9d50-8e6fd2f9ed0d",
  "timestamp": "2026-04-17T10:30:00+00:00",
  "path": "/v1/rescue-requests",
  "method": "POST",
  "details": [
    { "field": "contactPhone", "issue": "invalid phone number format" }
  ]
}
```

`details` is always present and is an empty array when there are no field-level issues.

| HTTP Status | Error Code | When |
|-------------|------------|------|
| `400` | `BAD_REQUEST` | Malformed request, invalid JSON, invalid query/header/path coercion |
| `403` | `FORBIDDEN` | Phone + tracking code combination is invalid |
| `404` | `NOT_FOUND` | Resource does not exist |
| `409` | `CONFLICT` | Invalid state transition / version mismatch / duplicate / idempotency key reused with different payload |
| `422` | `VALIDATION_ERROR` | Input validation failure (see `details`) |
| `500` | `INTERNAL_ERROR` | Unexpected server error |

---

## 5. Enumerations

### RequestStatus

| Value | Description |
|-------|-------------|
| `SUBMITTED` | Initial state — request received |
| `TRIAGED` | Request reviewed and verified by staff |
| `ASSIGNED` | Responder unit has been assigned |
| `IN_PROGRESS` | Rescue operation is underway |
| `RESOLVED` | *(terminal)* All persons assisted |
| `CANCELLED` | *(terminal)* Request cancelled |

### RequestType

`FLOOD` · `FIRE` · `EARTHQUAKE` · `LANDSLIDE` · `STORM` · `MEDICAL` · `EVACUATION` · `SUPPLY` · `OTHER`

### SourceChannel

`WEB` · `MOBILE` · `LINE` · `PHONE` · `WALK_IN` · `OTHER`

### UpdateType

| Value | Typical `updatePayload` |
|-------|------------------------|
| `NOTE` | `{ "note": "rescuers arrived" }` |
| `LOCATION_DETAILS` | `{ "locationDetails": "now on the roof" }` |
| `PEOPLE_COUNT` | `{ "peopleCount": 7 }` |
| `SPECIAL_NEEDS` | `{ "specialNeeds": "person with broken leg" }` |
| `CONTACT_INFO` | `{ "contactPhone": "0899999999" }` |

---

## 6. Public Endpoints (Citizens)

### 6.0 GET /health, /health/live, /health/ready

Health-check endpoints for infrastructure probes and monitoring.

| Endpoint | Purpose | Dependencies | Success | Failure |
|----------|---------|--------------|---------|---------|
| `GET /health/live` | Liveness probe (process is up) | none | `200` | `500` |
| `GET /health/ready` | Readiness probe (can serve traffic) | DynamoDB tables (`RescueRequestTable`, `IdempotencyTable`, `IncidentCatalogTable`) | `200` | `503` |
| `GET /health` | Combined summary (liveness + readiness) | same as readiness | `200` | `503` |

#### Example response (`GET /health`)

```json
{
  "service": "rescue-request-service",
  "stage": "dev",
  "region": "ap-southeast-2",
  "status": "pass",
  "timestamp": "2026-04-20T10:10:00+00:00",
  "checks": {
    "liveness": {
      "status": "pass",
      "uptimeMs": 15342
    },
    "readiness": {
      "status": "pass",
      "latencyMs": 25,
      "tables": [
        {
          "name": "rescueRequestTable",
          "tableName": "RescueRequestTable-dev",
          "status": "pass",
          "tableStatus": "ACTIVE",
          "latencyMs": 8,
          "issue": null
        }
      ]
    }
  }
}
```

### 6.1 POST /rescue-requests

Creates a new rescue request.

On success the service returns a short **tracking code** that the citizen can use later,
together with their phone number, to look up the status of their request.

**Phone uniqueness** — a `409 Conflict` is returned if `contactPhone` already exists
in any prior request.

**Duplicate detection** — additionally, a `409 Conflict` is returned if a request with
the same incident, phone, request type, approximate location, and submission time
(within a 5-minute window) already exists and no idempotency key was supplied.

#### Request

| Location | Field | Type | Required | Description |
|----------|-------|------|----------|-------------|
| Header | `X-Idempotency-Key` | UUID | No | Idempotency key |
| Body | `incidentId` | string | **Yes** | Disaster incident identifier; must exist in `IncidentCatalogTable` (status is ignored) |
| Body | `requestType` | RequestType | **Yes** | Type of emergency |
| Body | `description` | string | **Yes** | Free-text situation description |
| Body | `peopleCount` | integer = 1 | **Yes** | Number of people who need help |
| Body | `latitude` | number [-90, 90] | **Yes** | GPS latitude |
| Body | `longitude` | number [-180, 180] | **Yes** | GPS longitude |
| Body | `contactName` | string | **Yes** | Primary contact's full name |
| Body | `contactPhone` | string (7-20 chars) | **Yes** | Contact phone number. Current validation accepts digits, spaces, `+`, `-`, and parentheses. |
| Body | `sourceChannel` | SourceChannel | **Yes** | Submission channel |
| Body | `specialNeeds` | string \| string[] \| null | No | Medical/mobility requirements. The current implementation stores the provided value as-is for create/PATCH flows. |
| Body | `locationDetails` | string \| null | No | Additional location hints |
| Body | `province` | string \| null | No | Province / region |
| Body | `district` | string \| null | No | District |
| Body | `subdistrict` | string \| null | No | Sub-district |
| Body | `addressLine` | string \| null | No | Street address |

**Example request body:**
```json
{
  "incidentId": "INC-2024-001",
  "requestType": "FLOOD",
  "description": "Water level rising rapidly, 5 people trapped on second floor",
  "peopleCount": 5,
  "latitude": 13.7563,
  "longitude": 100.5018,
  "contactName": "Somchai Jaidee",
  "contactPhone": "0812345678",
  "sourceChannel": "MOBILE",
  "specialNeeds": "Elderly person, needs wheelchair",
  "locationDetails": "Yellow house next to the big banyan tree",
  "province": "Bangkok",
  "district": "Bang Rak",
  "subdistrict": "Bang Rak",
  "addressLine": "123 Silom Road"
}
```

#### Response `201 Created`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "trackingCode": "123456",
  "status": "SUBMITTED",
  "submittedAt": "2024-01-15T10:30:00.000000+00:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Unique request identifier |
| `trackingCode` | string | Short code for citizen self-service lookup |
| `status` | RequestStatus | Always `SUBMITTED` |
| `submittedAt` | ISO-8601 | UTC submission timestamp |

**Error responses:** `400` (invalid JSON), `409` (phone already exists / duplicate), `422` (validation)

---

### 6.2 POST /citizen/tracking/lookup

Looks up a rescue request using the citizen's phone number and tracking code.

#### Request Body

```json
{
  "contactPhone": "0812345678",
  "trackingCode": "123456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contactPhone` | string | **Yes** | Phone used when submitting |
| `trackingCode` | string | **Yes** | Code received after submission |

#### Response `200 OK`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "incidentId": "INC-2024-001"
}
```

**Error responses:** `400` (invalid JSON), `403` (phone/code combination invalid), `422` (missing fields)

---

### 6.3 GET /citizen/rescue-requests/{requestId}/status

Returns a detailed citizen-facing status snapshot for tracking progress.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `requestId` | UUID | Rescue request identifier |

#### Response `200 OK`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "incidentId": "INC-2024-001",
  "requestType": "FLOOD",
  "status": "ASSIGNED",
  "statusMessage": "?????????????????????????????? ??????????????????????????",
  "nextSuggestedAction": "????????????????????????????????????????",
  "description": "Water level rising rapidly, 5 people trapped on second floor",
  "peopleCount": 5,
  "specialNeeds": "Elderly person, needs wheelchair",
  "submittedAt": "2024-01-15T10:30:00.000000+00:00",
  "lastCitizenUpdateAt": "2024-01-15T10:45:00.000000+00:00",
  "contactName": "Somchai Jaidee",
  "contactPhoneMasked": "081****678",
  "location": {
    "latitude": 13.7563,
    "longitude": 100.5018,
    "locationDetails": "Yellow house next to the big banyan tree",
    "addressLine": "123 Silom Road",
    "province": "Bangkok",
    "district": "Bang Rak",
    "subdistrict": "Bang Rak"
  },
  "priorityLevel": "HIGH",
  "assignedUnitId": "UNIT-007",
  "assignedAt": "2024-01-15T11:00:00.000000+00:00",
  "latestNote": "Forwarded to responder unit",
  "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00",
  "stateVersion": 3,
  "latestEvent": {
    "eventId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "version": 3,
    "previousStatus": "TRIAGED",
    "newStatus": "ASSIGNED",
    "occurredAt": "2024-01-15T11:00:00.000000+00:00",
    "changeReason": null,
    "meta": {
      "dispatchChannel": "RADIO"
    },
    "priorityScore": 0.855,
    "responderUnitId": "UNIT-007"
  },
  "recentEvents": [
    {
      "eventId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "version": 3,
      "previousStatus": "TRIAGED",
      "newStatus": "ASSIGNED",
      "occurredAt": "2024-01-15T11:00:00.000000+00:00",
      "changeReason": null,
      "meta": {
        "dispatchChannel": "RADIO"
      },
      "priorityScore": 0.855,
      "responderUnitId": "UNIT-007"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | |
| `incidentId` | string | Incident identifier |
| `requestType` | RequestType | Original request category |
| `status` | RequestStatus | Current lifecycle status |
| `statusMessage` | string \| null | Human-readable status description |
| `nextSuggestedAction` | string \| null | Suggested action for the citizen |
| `description` | string \| null | Original request description |
| `peopleCount` | integer \| null | Latest known affected people count |
| `specialNeeds` | string \| string[] \| null | Special-needs details |
| `submittedAt` | ISO-8601 \| null | Initial submission time |
| `lastCitizenUpdateAt` | ISO-8601 \| null | Last citizen update timestamp |
| `contactName` | string \| null | Contact name on the request |
| `contactPhoneMasked` | string \| null | Masked contact phone number |
| `location` | object | Location snapshot from the request |
| `priorityLevel` | string \| null | Human-readable priority label |
| `assignedUnitId` | string \| null | Responding unit, if assigned |
| `assignedAt` | ISO-8601 \| null | Assignment timestamp |
| `latestNote` | string \| null | Latest tracking note |
| `lastUpdatedAt` | ISO-8601 \| null | Last state change timestamp |
| `stateVersion` | integer | Monotonically increasing version counter |
| `latestEvent` | object \| null | Most recent status event (includes `meta`) |
| `recentEvents` | array | Up to 5 latest status events (newest first) |

**Error responses:** `400` (invalid requestId format), `404`

---

### 6.4 POST /citizen/rescue-requests/{requestId}/updates

Submits additional information from the citizen after the initial request (e.g. updated
head count, changed location, or a note for responders).

Cannot be called when the request is in a terminal state (`RESOLVED` or `CANCELLED`).

#### Request

| Location | Field | Type | Required | Description |
|----------|-------|------|----------|-------------|
| Path | `requestId` | UUID | **Yes** | |
| Header | `X-Idempotency-Key` | UUID | No | Idempotency key |
| Body | `trackingCode` | string | **Yes** | Tracking code used to authorize the update |
| Body | `updateType` | UpdateType | **Yes** | Category of update |
| Body | `updatePayload` | object | **Yes** | Update-specific payload (see [UpdateType](#updatetype)) |

`updatePayload` is validated by `updateType`:
- `NOTE` -> requires `note` (non-empty string)
- `LOCATION_DETAILS` -> requires `locationDetails` (non-empty string)
- `PEOPLE_COUNT` -> requires `peopleCount` (integer > 0)
- `SPECIAL_NEEDS` -> requires `specialNeeds` (non-empty string)
- `CONTACT_INFO` -> requires at least one of `contactPhone` / `contactName`

**Example request body:**
```json
{
  "trackingCode": "123456",
  "updateType": "PEOPLE_COUNT",
  "updatePayload": { "peopleCount": 7 }
}
```

#### Response `201 Created`

```json
{
  "updateId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "updateType": "PEOPLE_COUNT",
  "createdAt": "2024-01-15T10:45:00.000000+00:00"
}
```

**Error responses:** `400` (invalid JSON / invalid requestId format), `403` (trackingCode invalid), `404`, `409` (terminal state), `422`

---

### 6.5 GET /citizen/rescue-requests/{requestId}/updates

Returns a paginated list of all citizen-submitted updates for a rescue request.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `since` | ISO-8601 | — | Only return updates created at or after this timestamp |

#### Response `200 OK`

```json
{
  "items": [
    {
      "updateId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "requestId": "550e8400-e29b-41d4-a716-446655440000",
      "updateType": "PEOPLE_COUNT",
      "updatePayload": { "peopleCount": 7 },
      "citizenAuthMethod": "tracking_code",
      "createdAt": "2024-01-15T10:45:00.000000+00:00"
    }
  ],
  "nextCursor": null
}
```

**Error responses:** `400` (invalid requestId / pagination / `since` format), `404` (request not found)

---

### 6.6 GET /incidents

Returns the locally stored incident catalog used by clients when selecting an incident.

This endpoint reads from the service database, not from IncidentTracking Service inline.
The catalog is refreshed asynchronously every 30 minutes, so temporary upstream sync
failures do not block client reads.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `status` | string | — | Filter by the locally stored incident status snapshot |

#### Response `200 OK`

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
      "lastSyncedAt": "2026-04-17T08:30:00+00:00"
    }
  ],
  "nextCursor": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `incidentId` | string | Incident ID from IncidentTracking Service |
| `incidentType` | string \| null | Incident category |
| `incidentName` | string | Stable local display name, generated as `IncidentA`, `IncidentB`, `IncidentC`, ... |
| `incidentSequence` | integer | Sequence number used to derive `incidentName` |
| `status` | string \| null | Latest incident status stored in the local catalog |
| `incidentDescription` | string \| null | Incident description from upstream |
| `remoteCreatedAt` | ISO-8601 \| null | Upstream incident creation time, if present |
| `remoteUpdatedAt` | ISO-8601 \| null | Upstream incident update time, if present |
| `lastSyncedAt` | ISO-8601 \| null | Last successful refresh time for this row |

**Error responses:** `400` (invalid pagination), `500`

---

## 7. Staff Endpoints

### 7.1 GET /rescue-requests/{requestId}

Retrieves full details of a rescue request.
`master` is the original first report (not overwritten by citizen updates),
`updateItems` is the list of citizen-submitted updates, and `currentState` is the latest state.
Optionally embeds the status-event history.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `includeEvents` | boolean | `false` | Embed status-event history |
| `includeCitizenUpdates` | boolean | `false` | Embed citizen-submitted updates |

#### Response `200 OK`

```json
{
  "master": {
    "requestId": "550e8400-e29b-41d4-a716-446655440000",
    "incidentId": "INC-2024-001",
    "requestType": "FLOOD",
    "description": "Water level rising rapidly, 5 people trapped on second floor",
    "peopleCount": 5,
    "specialNeeds": "Elderly person, needs wheelchair",
    "latitude": 13.7563,
    "longitude": 100.5018,
    "locationDetails": "Yellow house next to the big banyan tree",
    "province": "Bangkok",
    "district": "Bang Rak",
    "subdistrict": "Bang Rak",
    "addressLine": "123 Silom Road",
    "contactName": "Somchai Jaidee",
    "contactPhone": "0812345678",
    "sourceChannel": "MOBILE",
    "submittedAt": "2024-01-15T10:30:00.000000+00:00",
    "lastCitizenUpdateAt": null
  },
  "currentState": {
    "requestId": "550e8400-e29b-41d4-a716-446655440000",
    "incidentId": "INC-2024-001",
    "lastEventId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "stateVersion": 3,
    "status": "ASSIGNED",
    "priorityScore": 0.855,
    "priorityLevel": "HIGH",
    "assignedUnitId": "UNIT-007",
    "assignedAt": "2024-01-15T11:00:00.000000+00:00",
    "latestNote": "Team dispatched, ETA 15 minutes",
    "lastUpdatedBy": "dispatcher-01",
    "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00",
    "latestPriorityEvaluationId": "b26c6606-c16f-4f25-bb4c-3cd1c9f7005f",
    "latestPriorityReason": "Children and bedridden residents need urgent rescue.",
    "latestPriorityEvaluatedAt": "2026-04-17T00:04:30+00:00",
    "latestPriorityCorrelationId": "3df04bc4-1de3-49d0-a47c-b9e76d2bd36c",
    "lastPriorityIngestedAt": "2026-04-17T00:05:00+00:00"
  },
  "updateItems": [
    {
      "updateId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "requestId": "550e8400-e29b-41d4-a716-446655440000",
      "updateType": "PEOPLE_COUNT",
      "updatePayload": { "peopleCount": 7 },
      "citizenAuthMethod": "tracking_code",
      "createdAt": "2024-01-15T10:45:00.000000+00:00"
    }
  ]
}
```

When `includeEvents=true` an `"events"` array is added.
When `includeCitizenUpdates=true` a `"citizenUpdates"` array is also returned as a backward-compatible alias of `updateItems`.
`master.specialNeeds` can currently be a string, an array of strings, or `null`.
`currentState` includes the latest ingested prioritization evaluation metadata when available.

**Error responses:** `400` (invalid requestId format), `404`

---

### 7.2 PATCH /rescue-requests/{requestId}

Partially updates the master record of a rescue request.

**Allowed fields:** `description`, `peopleCount`, `specialNeeds`, `locationDetails`, `addressLine`

`specialNeeds` is not strictly shape-validated by the current PATCH implementation, so
existing records may contain a string, an array of strings, or `null`.

**Forbidden fields:** `incidentId`, `status`, `requestId` — returning these in the body causes `422`.

Cannot be called when the request is in a terminal state.

#### Request

| Location | Field | Type | Required | Description |
|----------|-------|------|----------|-------------|
| Path | `requestId` | UUID | **Yes** | |
| Header | `X-Idempotency-Key` | UUID | No | Idempotency key |
| Header | `If-Match` | integer | No | Accepted for forward compatibility, but the current PATCH implementation does not enforce version matching |
| Body | (any allowed field) | — | — | At least one field is required |

**Example request body:**
```json
{
  "description": "Updated: water level now at 1.5 m, 7 people trapped",
  "peopleCount": 7
}
```

#### Response `200 OK`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "updated": ["description", "peopleCount"]
}
```

`PATCH /rescue-requests/{requestId}` currently also publishes a `rescue-request.citizen-updated`
SNS event with `updateType: "PATCH"` and `updateId: "patch"`.

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409` (terminal state / idempotency conflict), `422`

---

### 7.3 GET /rescue-requests/{requestId}/events

Returns a paginated list of status-change events for a rescue request.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `sinceVersion` | integer | — | Only return events with version >= this value |
| `order` | `ASC` \| `DESC` | `ASC` | Sort order |

#### Response `200 OK`

```json
{
  "items": [
    {
      "eventId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "requestId": "550e8400-e29b-41d4-a716-446655440000",
      "previousStatus": "SUBMITTED",
      "newStatus": "TRIAGED",
      "changedBy": "dispatcher-01",
      "changedByRole": "dispatcher",
      "changeReason": "Request verified, forwarding to field team",
      "meta": null,
      "priorityScore": 0.75,
      "responderUnitId": null,
      "version": 2,
      "occurredAt": "2024-01-15T10:35:00.000000+00:00"
    }
  ],
  "nextCursor": null
}
```

**Error responses:** `400` (invalid requestId / pagination / `sinceVersion` / `order`)

---

### 7.4 POST /rescue-requests/{requestId}/events

Appends an arbitrary status-change event. For standard lifecycle transitions prefer the
dedicated [Command Endpoints](#8-command-endpoints-state-machine).

#### Request

| Location | Field | Type | Required | Description |
|----------|-------|------|----------|-------------|
| Path | `requestId` | UUID | **Yes** | |
| Header | `X-Idempotency-Key` | UUID | No | Idempotency key |
| Header | `If-Match` | integer | No | Expected `stateVersion` |
| Body | `newStatus` | RequestStatus | **Yes** | Target status |
| Body | `changedBy` | string | **Yes** | Staff member identifier |
| Body | `changedByRole` | string | **Yes** | Staff member role |
| Body | `reason` | string \| null | No | Stored on the event as `changeReason`; required when `newStatus=CANCELLED` |
| Body | `responderUnitId` | string \| null | No | Required when `newStatus=ASSIGNED` |
| Body | `priorityScore` | number \| null | No | Numerical priority score between `0` and `1` |
| Body | `priorityLevel` | string \| null | No | Human-readable priority label |
| Body | `note` | string \| null | No | Operational note |
| Body | `meta` | object \| null | No | Arbitrary additional metadata |

**Example request body:**
```json
{
  "newStatus": "TRIAGED",
  "changedBy": "staff-001",
  "changedByRole": "dispatcher",
  "reason": "Request verified, forwarding to field team"
}
```

#### Response `200 OK` — [StatusTransitionResponse](#statustransitionresponse)

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`, `422`

---

### 7.5 GET /rescue-requests/{requestId}/current

Returns the latest state snapshot for a rescue request.

#### Response `200 OK`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "incidentId": "INC-2024-001",
  "lastEventId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "stateVersion": 3,
  "status": "ASSIGNED",
  "priorityScore": 0.855,
  "priorityLevel": "HIGH",
  "assignedUnitId": "UNIT-007",
  "assignedAt": "2024-01-15T11:00:00.000000+00:00",
  "latestNote": "Team dispatched, ETA 15 minutes",
  "lastUpdatedBy": "staff-001",
  "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00",
  "latestPriorityEvaluationId": "b26c6606-c16f-4f25-bb4c-3cd1c9f7005f",
  "latestPriorityReason": "Children and bedridden residents need urgent rescue.",
  "latestPriorityEvaluatedAt": "2026-04-17T00:04:30+00:00",
  "latestPriorityCorrelationId": "3df04bc4-1de3-49d0-a47c-b9e76d2bd36c",
  "lastPriorityIngestedAt": "2026-04-17T00:05:00+00:00"
}
```

Prioritization-related fields on `currentState`:
- `latestPriorityEvaluationId`, `latestPriorityReason`, `latestPriorityEvaluatedAt`, `latestPriorityCorrelationId`, `lastPriorityIngestedAt` track the latest evaluated result ingested back into the request.

**Error responses:** `400` (invalid requestId format), `404`

---

### 7.6 GET /incidents/{incidentId}/rescue-requests

Returns a paginated list of rescue requests for the given incident.
Each item is the master request record enriched with the latest `status` and a
`currentState` snapshot.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `status` | RequestStatus | — | Filter by latest `currentState.status` when available |

#### Response `200 OK`

```json
{
  "items": [
    {
      "requestId": "550e8400-e29b-41d4-a716-446655440000",
      "incidentId": "INC-2024-001",
      "status": "ASSIGNED",
      "requestType": "FLOOD",
      "description": "Water level rising rapidly, 5 people trapped on second floor",
      "peopleCount": 5,
      "specialNeeds": "Elderly person, needs wheelchair",
      "latitude": 13.7563,
      "longitude": 100.5018,
      "locationDetails": "Yellow house next to the big banyan tree",
      "province": "Bangkok",
      "district": "Bang Rak",
      "subdistrict": "Bang Rak",
      "addressLine": "123 Silom Road",
      "contactName": "Somchai Jaidee",
      "contactPhone": "0812345678",
      "sourceChannel": "MOBILE",
      "submittedAt": "2024-01-15T10:30:00.000000+00:00",
      "lastCitizenUpdateAt": "2024-01-15T10:45:00.000000+00:00",
      "currentState": {
        "requestId": "550e8400-e29b-41d4-a716-446655440000",
        "incidentId": "INC-2024-001",
        "lastEventId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "stateVersion": 3,
        "status": "ASSIGNED",
        "priorityScore": 0.855,
        "priorityLevel": "HIGH",
        "assignedUnitId": "UNIT-007",
        "assignedAt": "2024-01-15T11:00:00.000000+00:00",
        "latestNote": "Team dispatched, ETA 15 minutes",
        "lastUpdatedBy": "dispatcher-01",
        "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00",
        "latestPriorityEvaluationId": "b26c6606-c16f-4f25-bb4c-3cd1c9f7005f",
        "latestPriorityReason": "Children and bedridden residents need urgent rescue.",
        "latestPriorityEvaluatedAt": "2026-04-17T00:04:30+00:00",
        "latestPriorityCorrelationId": "3df04bc4-1de3-49d0-a47c-b9e76d2bd36c",
        "lastPriorityIngestedAt": "2026-04-17T00:05:00+00:00"
      }
    }
  ],
  "nextCursor": null
}
```

**Error responses:** `400` (invalid pagination / invalid status filter)

---

### 7.7 GET /idempotency-keys/{idempotencyKeyHash}

Retrieves the stored idempotency record for a given SHA-256 key hash. Useful for
debugging replayed or in-flight requests.

#### Path Parameters

| Parameter | Description |
|-----------|-------------|
| `idempotencyKeyHash` | SHA-256 hash of the original `X-Idempotency-Key` value |

#### Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `includeResponse` | `false` | Include `responseStatusCode` and `responseBody` |
| `includeRequestFingerprint` | `false` | Include SHA-256 fingerprint of original request body |

#### Response `200 OK`

```json
{
  "idempotencyKeyHash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
  "operationName": "CreateRescueRequest",
  "status": "COMPLETED",
  "createdAt": "2024-01-15T10:30:00.000000+00:00",
  "updatedAt": "2024-01-15T10:30:01.000000+00:00",
  "resultResourceId": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Description |
|-------|-------------|
| `status` | `IN_PROGRESS` / `COMPLETED` / `FAILED` |
| `resultResourceId` | ID of the resource that was created or modified |
| `responseStatusCode` | *(only when `includeResponse=true`)* |
| `responseBody` | *(only when `includeResponse=true`)* |
| `requestFingerprint` | *(only when `includeRequestFingerprint=true`)* |

**Error responses:** `404`

---

### 7.8 PATCH /rescue-requests/{requestId}/priority

Synchronously updates priority-related fields on the request's `currentState`.

**Editable fields:** `priorityScore`, `priorityLevel`, `note`  
(`note` is stored internally as `latestNote` on `currentState`)

At least one editable field must be present.
Cannot be called when the request is in a terminal state (`RESOLVED` or `CANCELLED`).

#### Request

| Location | Field | Type | Required | Description |
|----------|-------|------|----------|-------------|
| Path | `requestId` | UUID | **Yes** | |
| Header | `X-Idempotency-Key` | UUID | No | Idempotency key |
| Header | `If-Match` | integer | No | Expected `stateVersion` for optimistic concurrency check |
| Body | `priorityScore` | number \| null | No | New numerical priority score between `0` and `1` |
| Body | `priorityLevel` | string \| null | No | New human-readable priority label |
| Body | `note` | string \| null | No | New operational note |

**Example request body:**
```json
{
  "priorityScore": 0.925,
  "priorityLevel": "CRITICAL",
  "note": "Escalated after reassessment"
}
```

#### Response `200 OK`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "priorityScore": 0.925,
  "priorityLevel": "CRITICAL",
  "note": "Escalated after reassessment",
  "updatedAt": "2024-01-15T11:05:00.000000+00:00",
  "updated": ["priorityScore", "priorityLevel", "note"]
}
```

When `priorityScore` changes, the service publishes a
`rescue-request.priority-score-updated` SNS event.

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`, `422`

---

## 8. Command Endpoints (State Machine)

All command endpoints share the same response shape ([StatusTransitionResponse](#statustransitionresponse))
and accept the same optional headers (`X-Idempotency-Key`, `If-Match`).
If `changedBy` or `changedByRole` is omitted on command endpoints, the current implementation
defaults both values to `"staff"`.

### StatusTransitionResponse

```json
{
  "eventId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "previousStatus": "SUBMITTED",
  "newStatus": "TRIAGED",
  "version": 2,
  "occurredAt": "2024-01-15T10:35:00.000000+00:00"
}
```

| Field | Description |
|-------|-------------|
| `eventId` | UUID of the new status-change event |
| `requestId` | UUID of the rescue request |
| `previousStatus` | Status before the transition |
| `newStatus` | Status after the transition |
| `version` | New `stateVersion` |
| `occurredAt` | ISO-8601 timestamp |

---

### 8.1 POST /rescue-requests/{requestId}/triage

`SUBMITTED ? TRIAGED`

#### Request Body (optional)

| Field | Type | Description |
|-------|------|-------------|
| `changedBy` | string | Staff identifier (default: `"staff"`) |
| `changedByRole` | string | Staff role (default: `"staff"`) |
| `priorityScore` | number \| null | Numerical priority between `0` and `1` |
| `priorityLevel` | string \| null | Human-readable priority label |
| `note` | string \| null | Operational note |
| `meta` | object \| null | Additional metadata |

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`

---

### 8.2 POST /rescue-requests/{requestId}/assign

`SUBMITTED ? ASSIGNED` or `TRIAGED ? ASSIGNED`

**`responderUnitId` is required.**

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `responderUnitId` | string | **Yes** | Responding unit identifier |
| `changedBy` | string | No | Staff identifier |
| `changedByRole` | string | No | Staff role |
| `priorityScore` | number \| null | No | Numerical priority score between `0` and `1` |
| `priorityLevel` | string \| null | No | |
| `note` | string \| null | No | |
| `meta` | object \| null | No | |

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`, `422`

---

### 8.3 POST /rescue-requests/{requestId}/start

`ASSIGNED ? IN_PROGRESS`

#### Request Body (optional)

Same optional fields as [triage](#81-post-rescue-requestsrequestidtriage).

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`

---

### 8.4 POST /rescue-requests/{requestId}/resolve

`IN_PROGRESS ? RESOLVED` *(terminal)*

Publishes `rescue-request.status-changed` and `rescue-request.resolved` SNS events.

#### Request Body (optional)

Same optional fields as [triage](#81-post-rescue-requestsrequestidtriage).

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`

---

### 8.5 POST /rescue-requests/{requestId}/cancel

`* ? CANCELLED` *(terminal — from any non-terminal state)*

Publishes `rescue-request.status-changed` and `rescue-request.cancelled` SNS events.

**`reason` is required.**

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reason` | string | **Yes** | Cancellation reason |
| `changedBy` | string | No | Staff identifier |
| `changedByRole` | string | No | Staff role |
| `meta` | object \| null | No | Additional metadata |

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`, `422`

---

## 9. State Machine

```
SUBMITTED --/triage--? TRIAGED --/assign--? ASSIGNED --/start--? IN_PROGRESS --/resolve--? RESOLVED
    ¦                     ¦                     ¦                      ¦
    +------/assign--------?                     ¦                      ¦
    +----------------------------------------------------------------------/cancel--? CANCELLED
```

### Allowed Transitions

| From | To | Command |
|------|----|---------|
| `SUBMITTED` | `TRIAGED` | `/triage` |
| `SUBMITTED` | `ASSIGNED` | `/assign` |
| `TRIAGED` | `ASSIGNED` | `/assign` |
| `ASSIGNED` | `IN_PROGRESS` | `/start` |
| `IN_PROGRESS` | `RESOLVED` | `/resolve` |
| `SUBMITTED` | `CANCELLED` | `/cancel` |
| `TRIAGED` | `CANCELLED` | `/cancel` |
| `ASSIGNED` | `CANCELLED` | `/cancel` |
| `IN_PROGRESS` | `CANCELLED` | `/cancel` |

Attempting an invalid transition returns `409 Conflict`.
Attempting to transition from a terminal state (`RESOLVED` or `CANCELLED`) also returns `409 Conflict`.

### Required Fields per Transition

| Target Status | Required Field |
|---------------|---------------|
| `ASSIGNED` | `responderUnitId` |
| `CANCELLED` | `reason` |

---

## 10. Async Contract

This section defines the service-owned async contract published by Rescue Request Service.

Primary topic:

- `rescue-request-events-v1-{stage}`

### 10.1 Envelope Contract (All Outbound Messages)

```json
{
  "header": {
    "messageId": "uuid",
    "eventType": "rescue-request.status-changed",
    "schemaVersion": "1.0",
    "producer": "rescue-request-service",
    "occurredAt": "2026-04-20T15:30:00.000000+00:00",
    "traceId": "uuid",
    "correlationId": "uuid",
    "partitionKey": "requestId",
    "contentType": "application/json"
  },
  "body": {}
}
```

Common header fields:

| Header | Type | Description |
|--------|------|-------------|
| `header.messageId` | UUID | Unique event id |
| `header.eventType` | string | Event name |
| `header.schemaVersion` | string | Fixed `1.0` |
| `header.producer` | string | Fixed `rescue-request-service` |
| `header.occurredAt` | ISO-8601 datetime | Publish time |
| `header.traceId` | UUID | Trace identifier |
| `header.correlationId` | UUID/string | Correlation value for downstream flow |
| `header.partitionKey` | string | Partition key (request id) |
| `header.contentType` | string | Fixed `application/json` |

SNS message attributes:

| Attribute | Value |
|-----------|-------|
| `eventType` | same as `header.eventType` |
| `schemaVersion` | `1.0` |
| `producer` | `rescue-request-service` |

### 10.2 Primary Message Set (5 Messages)

#### Message #1 - `rescue-request.created`

| Item | Value |
|------|-------|
| Style | Event (Pub/Sub) |
| Producer | Rescue Request Service |
| Main Consumer | Rescue Request Prioritization Service |
| Trigger | `POST /rescue-requests` success |
| Correlation | Explicitly set to `requestId` |

Body contract:

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Request id |
| `data` | object | Full persisted master request snapshot at creation time (includes service-internal storage fields) |

Message body example:

```json
{
  "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "data": {
    "PK": "REQ#0933d4b5-2845-4da6-9aed-f2f341e0ee71",
    "SK": "META",
    "itemType": "MASTER",
    "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
    "incidentId": "f3e1c8b2-6a1d-4c22-a9f3-5f8b7a1d2e10",
    "requestType": "FLOOD",
    "description": "ระดับน้ำเพิ่มสูงอย่างรวดเร็ว",
    "peopleCount": 2,
    "latitude": 13.7563,
    "longitude": 100.5018,
    "contactName": "สมชาย ใจดี",
    "contactPhone": "0812345678",
    "sourceChannel": "MOBILE",
    "submittedAt": "2026-04-20T16:05:10.111222+00:00"
  }
}
```

Published header example:

```json
{
  "messageId": "2df36ac2-93eb-4f6f-bf8d-5bb46bf6fb75",
  "eventType": "rescue-request.created",
  "schemaVersion": "1.0",
  "producer": "rescue-request-service",
  "occurredAt": "2026-04-20T16:05:12.451289+00:00",
  "traceId": "3b7fa0cb-c27c-42c7-af4a-6f4fae87bd41",
  "correlationId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "partitionKey": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "contentType": "application/json"
}
```

Published header fields:

| Header | Value / Rule |
|--------|--------------|
| `messageId` | UUID generated by service |
| `eventType` | fixed `rescue-request.created` |
| `schemaVersion` | fixed `1.0` |
| `producer` | fixed `rescue-request-service` |
| `occurredAt` | publish timestamp (ISO-8601) |
| `traceId` | UUID generated by service unless explicitly supplied |
| `correlationId` | set to `requestId` in create flow |
| `partitionKey` | `requestId` |
| `contentType` | fixed `application/json` |

#### Message #2 - `rescue-request.citizen-updated`

| Item | Value |
|------|-------|
| Style | Event (Pub/Sub) |
| Producer | Rescue Request Service |
| Main Consumer | Rescue Request Prioritization Service |
| Trigger | `POST /citizen/rescue-requests/{requestId}/updates` and `PATCH /rescue-requests/{requestId}` |
| Correlation | Auto-generated UUID when not explicitly supplied |

Body contract:

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Request id |
| `updateId` | string | Update identifier (`patch` for staff patch flow) |
| `updateType` | string | Citizen flow: one of update types; patch flow: `PATCH` |
| `updatePayload` | object | Changed payload (present in both citizen update and patch publisher paths) |
| `createdAt` | ISO-8601 datetime | Present in citizen update flow |

Message body example:

```json
{
  "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "updateId": "30c71f17-4f72-4bb6-b6c2-8f6e12f8f3d2",
  "updateType": "PEOPLE_COUNT",
  "updatePayload": {
    "peopleCount": 5
  },
  "createdAt": "2026-04-20T16:08:00.000000+00:00"
}
```

Published header example:

```json
{
  "messageId": "8f3a6771-16f2-4f7a-9f6a-90e36dd0db5c",
  "eventType": "rescue-request.citizen-updated",
  "schemaVersion": "1.0",
  "producer": "rescue-request-service",
  "occurredAt": "2026-04-20T16:08:01.133052+00:00",
  "traceId": "25a36dc1-916f-4c69-8b9d-c8b6fa84c3ef",
  "correlationId": "7ccfe913-0ec9-45eb-aeef-64380d62f2de",
  "partitionKey": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "contentType": "application/json"
}
```

Published header fields:

| Header | Value / Rule |
|--------|--------------|
| `messageId` | UUID generated by service |
| `eventType` | fixed `rescue-request.citizen-updated` |
| `schemaVersion` | fixed `1.0` |
| `producer` | fixed `rescue-request-service` |
| `occurredAt` | publish timestamp (ISO-8601) |
| `traceId` | UUID generated by service unless explicitly supplied |
| `correlationId` | auto-generated UUID when not supplied |
| `partitionKey` | `requestId` |
| `contentType` | fixed `application/json` |

#### Message #3 - `rescue-request.status-changed`

| Item | Value |
|------|-------|
| Style | Event (Pub/Sub) |
| Producer | Rescue Request Service |
| Main Consumer | Stream consumers, dashboards, automation |
| Trigger | Any successful state transition (commands, append-event flow, prioritization ingest flow) |
| Correlation | Depends on source flow (command default auto UUID, append-event may use requestId, prioritization ingest forwards inbound correlation) |

Body contract:

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Request id |
| `previousStatus` | enum | Previous status |
| `newStatus` | enum | New status |
| `eventId` | UUID | Status event id |
| `version` | integer | New `stateVersion` |

Message body example:

```json
{
  "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "previousStatus": "SUBMITTED",
  "newStatus": "TRIAGED",
  "eventId": "95f49f58-c495-4e87-bd74-8dae36f65f9e",
  "version": 2
}
```

Published header example:

```json
{
  "messageId": "f6cc2ad2-570b-49a2-87b4-a1009fd5f7cf",
  "eventType": "rescue-request.status-changed",
  "schemaVersion": "1.0",
  "producer": "rescue-request-service",
  "occurredAt": "2026-04-20T16:10:15.557404+00:00",
  "traceId": "6a7f85cc-d2d0-4487-8ab5-7f8cc85e08bb",
  "correlationId": "d0b1c2d3-e4f5-6789-a0b1-c2d3e4f56789",
  "partitionKey": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "contentType": "application/json"
}
```

Published header fields:

| Header | Value / Rule |
|--------|--------------|
| `messageId` | UUID generated by service |
| `eventType` | fixed `rescue-request.status-changed` |
| `schemaVersion` | fixed `1.0` |
| `producer` | fixed `rescue-request-service` |
| `occurredAt` | publish timestamp (ISO-8601) |
| `traceId` | UUID generated by service unless explicitly supplied |
| `correlationId` | source dependent: auto UUID, `requestId`, or forwarded inbound correlation (prioritization ingest) |
| `partitionKey` | `requestId` |
| `contentType` | fixed `application/json` |

#### Message #4 - `rescue-request.resolved`

| Item | Value |
|------|-------|
| Style | Event (Pub/Sub) |
| Producer | Rescue Request Service |
| Main Consumer | Stream consumers, closure automation |
| Trigger | Transition to `RESOLVED` (published in addition to `rescue-request.status-changed`) |

Body contract:

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Request id |
| `eventId` | UUID | Closure event id |

Message body example:

```json
{
  "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "eventId": "db1f16c5-d01d-43b8-8ca6-2bcbf9147633"
}
```

Published header example:

```json
{
  "messageId": "6f6b6052-c650-426f-a126-68f7b6210e79",
  "eventType": "rescue-request.resolved",
  "schemaVersion": "1.0",
  "producer": "rescue-request-service",
  "occurredAt": "2026-04-20T16:13:42.011927+00:00",
  "traceId": "bc37f2f4-6f08-45c8-8b3f-29d7d1ad0f6f",
  "correlationId": "f640a544-cf83-4b61-9b8b-8a8026689792",
  "partitionKey": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "contentType": "application/json"
}
```

Published header fields:

| Header | Value / Rule |
|--------|--------------|
| `messageId` | UUID generated by service |
| `eventType` | fixed `rescue-request.resolved` |
| `schemaVersion` | fixed `1.0` |
| `producer` | fixed `rescue-request-service` |
| `occurredAt` | publish timestamp (ISO-8601) |
| `traceId` | UUID generated by service unless explicitly supplied |
| `correlationId` | auto-generated UUID when not supplied |
| `partitionKey` | `requestId` |
| `contentType` | fixed `application/json` |

#### Message #5 - `rescue-request.cancelled`

| Item | Value |
|------|-------|
| Style | Event (Pub/Sub) |
| Producer | Rescue Request Service |
| Main Consumer | Stream consumers, closure automation |
| Trigger | Transition to `CANCELLED` (published in addition to `rescue-request.status-changed`) |

Body contract:

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Request id |
| `eventId` | UUID | Cancellation event id |
| `reason` | string | Cancellation reason (can be empty string if not provided by caller) |

Message body example:

```json
{
  "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "eventId": "4a3e4c72-8f76-4cea-a30e-1bf2a0d7e4af",
  "reason": "Duplicate submission confirmed by operator"
}
```

Published header example:

```json
{
  "messageId": "3bb3b113-76d1-4139-9e6c-86c05f9aa6ce",
  "eventType": "rescue-request.cancelled",
  "schemaVersion": "1.0",
  "producer": "rescue-request-service",
  "occurredAt": "2026-04-20T16:15:18.771211+00:00",
  "traceId": "8f442823-dcd0-4a64-96a9-11b66f2d4984",
  "correlationId": "6169fde9-d4fb-4d6a-ab0e-3cb7db663d90",
  "partitionKey": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "contentType": "application/json"
}
```

Published header fields:

| Header | Value / Rule |
|--------|--------------|
| `messageId` | UUID generated by service |
| `eventType` | fixed `rescue-request.cancelled` |
| `schemaVersion` | fixed `1.0` |
| `producer` | fixed `rescue-request-service` |
| `occurredAt` | publish timestamp (ISO-8601) |
| `traceId` | UUID generated by service unless explicitly supplied |
| `correlationId` | auto-generated UUID when not supplied |
| `partitionKey` | `requestId` |
| `contentType` | fixed `application/json` |

### 10.3 Additional Outbound Event (Operational)

#### Message #6 - `rescue-request.priority-score-updated`

| Item | Value |
|------|-------|
| Style | Event (Pub/Sub) |
| Producer | Rescue Request Service |
| Main Consumer | Stream consumers, analytics, monitoring |
| Trigger | `PATCH /rescue-requests/{requestId}/priority` when `priorityScore` actually changes |
| Correlation | Explicitly set to `requestId` in this flow |

Body contract:

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | Request id |
| `previousPriorityScore` | number \| null | Score before update |
| `newPriorityScore` | number \| null | Score after update |
| `priorityLevel` | string | Priority level after update |
| `note` | string | Staff note |
| `updatedAt` | ISO-8601 datetime | Update timestamp |

Message body example:

```json
{
  "requestId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "previousPriorityScore": 0.6,
  "newPriorityScore": 0.9,
  "priorityLevel": "CRITICAL",
  "note": "Escalated after manual validation",
  "updatedAt": "2026-04-20T16:17:19.000000+00:00"
}
```

Published header example:

```json
{
  "messageId": "7a4fce95-4960-44f0-b2b6-790c0fd08957",
  "eventType": "rescue-request.priority-score-updated",
  "schemaVersion": "1.0",
  "producer": "rescue-request-service",
  "occurredAt": "2026-04-20T16:17:20.782000+00:00",
  "traceId": "fcfc3c44-6898-4c1a-8784-66effd8e9599",
  "correlationId": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "partitionKey": "0933d4b5-2845-4da6-9aed-f2f341e0ee71",
  "contentType": "application/json"
}
```

Published header fields:

| Header | Value / Rule |
|--------|--------------|
| `messageId` | UUID generated by service |
| `eventType` | fixed `rescue-request.priority-score-updated` |
| `schemaVersion` | fixed `1.0` |
| `producer` | fixed `rescue-request-service` |
| `occurredAt` | publish timestamp (ISO-8601) |
| `traceId` | UUID generated by service unless explicitly supplied |
| `correlationId` | set to `requestId` in priority update flow |
| `partitionKey` | `requestId` |
| `contentType` | fixed `application/json` |

---

## 11. Async Integrations

### 11.1 Prioritization Result Ingest

This service consumes evaluated prioritization results from Rescue Request Prioritization Service.

Queue topology:

- queue: `rescue-prioritization-evaluated-{stage}`
- DLQ: `rescue-prioritization-evaluated-dlq-{stage}`

External topics that can fan in to the shared queue:

- `rescue.prioritization.created.v1`
- `rescue.prioritization.updated.v1`
- `rescue.prioritization.events.v1` (consolidated topic)

Optional stack parameters for auto-subscription:

- `PrioritizationCreatedTopicArn`
- `PrioritizationUpdatedTopicArn`

Inbound `messageType` compatibility:

- `RescueRequestEvaluatedEvent` (canonical)
- `RescueRequestEvaluateEvent` (compatibility alias, normalized to canonical)
- `RescueRequestReEvaluateEvent` (accepted on updated/consolidated result channels)

#### Example Integration Reference - Message #3 Rescue Request Update Flow

Reference use case: citizen/staff update triggers re-evaluation in Prioritization Service.

| Item | Value |
|------|-------|
| Source Message Name | `rescue-request.citizen-updated` |
| Source Producer | Rescue Request Service |
| Source Consumer | Rescue Request Prioritization Service |
| Result Channel | `rescue.prioritization.updated.v1` |
| Result `messageType` | `RescueRequestReEvaluateEvent` |
| Description | ????? request ??? update (????????????????????????????????? location ???????) Prioritization Service ??????????????????????? service ??? ingest |

Result message headers:

| Header | Description |
|--------|-------------|
| `messageType` | `RescueRequestEvaluatedEvent` / `RescueRequestEvaluateEvent` / `RescueRequestReEvaluateEvent` |
| `correlationId` | Must match `CURRENT_STATE.latestPrioritySourceEventId` |
| `sentAt` | ISO-8601 datetime |
| `version` | `1` |

Result body example:

```json
{
  "requestId": "REQ-8812-8888",
  "incidentId": "8b9b6d5b-7d5e-4d0b-a7e2-2a0a6bd5c111",
  "evaluateId": "812748a6-5a3a-43c5-8b4f-140034ece737",
  "requestType": "flood_rescue",
  "priorityScore": 0.3,
  "priorityLevel": "NORMAL",
  "evaluateReason": "Lack of food reserves indicates a potential need for assistance, but no immediate life-threatening situation is apparent. Location is accessible.",
  "lastEvaluatedAt": "2026-03-22T07:58:10.247935+00:00",
  "description": "????????????????",
  "location": {
    "latitude": 11.111,
    "longitude": 22.222,
    "province": "test province",
    "district": "test dist",
    "subdistrict": "test subdist",
    "addressLine": "test address"
  },
  "peopleCount": 1,
  "specialNeeds": [
    "bedridden",
    "children"
  ]
}
```

Required inbound fields:

- `header.messageType`
- `header.correlationId`
- `header.sentAt`
- `header.version`
- `body.requestId`
- `body.incidentId`
- `body.evaluateId`
- `body.requestType`
- `body.priorityScore`
- `body.priorityLevel`
- `body.evaluateReason`
- `body.lastEvaluatedAt`
- `body.description`
- `body.location.latitude`
- `body.location.longitude`
- `body.peopleCount`

Validation rules:

- `incidentId` and `evaluateId` must be valid UUIDs
- `priorityScore` must be between `0` and `1`
- `priorityLevel` must be one of `LOW`, `NORMAL`, `HIGH`, `CRITICAL`
- `submittedAt`, when present, must be ISO-8601 datetime
- `location` must exist with numeric `latitude` and `longitude`
- `correlationId` must match latest service-owned priority source event id

Accepted result behavior:

- appends `EVENT#{stateVersion}`
- bumps `stateVersion`
- updates priority fields in `CURRENT`
- publishes `rescue-request.status-changed`
- skips terminal requests
- applies idempotency key `RescueRequestEvaluatedEvent#{evaluateId}`

### 11.2 Incident Catalog Sync

Incident data is synchronized from IncidentTracking Service into local `IncidentCatalogTable-{stage}`.

| Item | Value |
|------|-------|
| Trigger | EventBridge schedule `rate(30 minutes)` |
| Lambda timeout | 30 seconds |
| External HTTP timeout | 30 seconds |
| Secret source | AWS Secrets Manager `rescue-request-service/incident-tracking/{stage}` |
| Required secret keys | `apiUrl`, `apiKey` |
| Optional secret keys | `accept`, `transactionIdHeader` |

Client read behavior:

- `GET /incidents` reads from local table only
- `GET /internal/incidents/catalog` reads from local table only
- upstream sync failure does not block read availability

---

## 12. Idempotency

### Usage

Include the `X-Idempotency-Key` header with any UUID v4 value on mutating requests:

```
X-Idempotency-Key: f47ac10b-58cc-4372-a567-0e02b2c3d479
```

### Behaviour

| Scenario | Result |
|----------|--------|
| New key | Executes the operation, stores the result, returns the response |
| Same key + same payload (within TTL) | Returns the stored response without re-executing |
| Same key + different payload | `409 Conflict` |
| Key expired (> 24 h) | Treated as a new key |

### Supported Endpoints

| Endpoint | Operation Name |
|----------|---------------|
| `POST /rescue-requests` | `CreateRescueRequest` |
| `POST /citizen/rescue-requests/{requestId}/updates` | `CreateCitizenUpdate` |
| `PATCH /rescue-requests/{requestId}` | `PatchRescueRequest` |
| `PATCH /rescue-requests/{requestId}/priority` | `UpdateRescueRequestPriority` |
| `POST /rescue-requests/{requestId}/events` | `AppendStatusEvent` |
| `POST /rescue-requests/{requestId}/triage` | `Triage` |
| `POST /rescue-requests/{requestId}/assign` | `Assign` |
| `POST /rescue-requests/{requestId}/start` | `Start` |
| `POST /rescue-requests/{requestId}/resolve` | `Resolve` |
| `POST /rescue-requests/{requestId}/cancel` | `Cancel` |

### Configuration

| Setting | Value |
|---------|-------|
| TTL | 24 hours |
| Lock timeout | 5 minutes |
| Max reserve retries | 3 |

---

## 13. Duplicate Detection

When a request is submitted **without** an idempotency key, the service checks for a
recent duplicate using a content-based signature:

```
signature = SHA256(incidentId | normalizedPhone | requestType | geohash(lat,lng,precision=7) | timeBucket)
```

`timeBucket` divides submissions into **5-minute windows** so that a citizen can submit
a new request for the same situation once the window expires.

If a matching signature is found the service returns `409 Conflict` with the ID of the
existing request.

> Duplicate detection is **bypassed** when an `X-Idempotency-Key` header is present.
> Idempotent retries are always safe.
>
> Phone uniqueness by `contactPhone` is still enforced globally.

---

## 14. Internal Endpoints

### 14.1 GET /internal/incidents/catalog

Returns every row currently stored in `IncidentCatalogTable` for internal tooling/support use.

This endpoint returns the service's narrow internal shape and includes both:
- incidents currently stored in `IncidentCatalogTable` from sync operations

#### Response `200 OK`

```json
{
  "items": [
    {
      "incident_id": "019C774D-1AC5-758B-AE95-5CD4AEB89258",
      "incident_type": "flood",
      "incident_name": "IncidentA",
      "status": "REPORTED",
      "incident_description": "Flooding reported near main road and residential alley"
    },
    {
      "incident_id": "5c6f3f4d-2c67-4c78-9caa-4df94cbf6ec1",
      "incident_type": "fire",
      "incident_name": "IncidentB",
      "status": "REPORTED",
      "incident_description": "Fire reported near TU Dome (Verified)"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `incident_id` | string | Incident identifier stored in `IncidentCatalogTable` |
| `incident_type` | string \| null | Incident type stored in the table |
| `incident_name` | string \| null | Display name stored in the table |
| `status` | string \| null | Status stored in the table |
| `incident_description` | string \| null | Description stored in the table |

**Error responses:** `500`

