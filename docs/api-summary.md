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
10. [Async Integrations](#10-async-integrations)
11. [Idempotency](#11-idempotency)
12. [Duplicate Detection](#12-duplicate-detection)
13. [Internal Endpoints](#13-internal-endpoints)
   - [GET /internal/incidents/catalog](#131-get-internalincidentscatalog)

---

## 1. Overview

The Rescue Request Service provides a REST API for managing disaster rescue requests.
It also exposes a local incident catalog for request creation. That catalog is refreshed
asynchronously from IncidentTracking Service every 30 minutes, while the API itself reads
from the service database snapshot. The incident catalog table is also bootstrapped with
five hardmock rows (`IncidentA` through `IncidentE`) for internal testing and UI bootstrap.

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
| Body | `incidentId` | string | **Yes** | Disaster incident identifier |
| Body | `requestType` | RequestType | **Yes** | Type of emergency |
| Body | `description` | string | **Yes** | Free-text situation description |
| Body | `peopleCount` | integer ≥ 1 | **Yes** | Number of people who need help |
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
  "statusMessage": "มีการมอบหมายหน่วยช่วยเหลือแล้ว กรุณาติดตามการอัปเดตล่าสุด",
  "nextSuggestedAction": "เตรียมพร้อมรับการติดต่อจากหน่วยช่วยเหลือ",
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
The table is also bootstrapped with five hardmock rows `IncidentA` through `IncidentE`.

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

`SUBMITTED → TRIAGED`

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

`SUBMITTED → ASSIGNED` or `TRIAGED → ASSIGNED`

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

`ASSIGNED → IN_PROGRESS`

#### Request Body (optional)

Same optional fields as [triage](#81-post-rescue-requestsrequestidtriage).

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`

---

### 8.4 POST /rescue-requests/{requestId}/resolve

`IN_PROGRESS → RESOLVED` *(terminal)*

Publishes `rescue-request.status-changed` and `rescue-request.resolved` SNS events.

#### Request Body (optional)

Same optional fields as [triage](#81-post-rescue-requestsrequestidtriage).

**Error responses:** `400` (invalid JSON / invalid requestId / invalid `If-Match`), `404`, `409`

---

### 8.5 POST /rescue-requests/{requestId}/cancel

`* → CANCELLED` *(terminal — from any non-terminal state)*

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
SUBMITTED ──/triage──▶ TRIAGED ──/assign──▶ ASSIGNED ──/start──▶ IN_PROGRESS ──/resolve──▶ RESOLVED
    │                     │                     │                      │
    ├──────/assign────────▶                     │                      │
    └──────────────────────┴─────────────────────┴──────────────────────┴──/cancel──▶ CANCELLED
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

## 10. Async Integrations

**Topic:** `rescue-request-events-v1-{stage}`

The internal `/stream` relay may normalize or repackage events for SSE delivery.
That relay shape is internal-only and should not be treated as a public contract.

Raw SNS messages are wrapped in the following envelope:

```json
{
  "header": {
    "messageId": "uuid",
    "eventType": "rescue-request.status-changed",
    "schemaVersion": "1.0",
    "producer": "rescue-request-service",
    "occurredAt": "2024-01-15T10:35:00.000000+00:00",
    "traceId": "uuid",
    "correlationId": "uuid",
    "partitionKey": "550e8400-e29b-41d4-a716-446655440000",
    "contentType": "application/json"
  },
  "body": { }
}
```

**SNS Message Attributes** (usable for subscription filters):

| Attribute | Value |
|-----------|-------|
| `eventType` | e.g. `rescue-request.created` |
| `schemaVersion` | `1.0` |
| `producer` | `rescue-request-service` |

### Published Events

| Event Type | Trigger | `body` Fields |
|------------|---------|--------------|
| `rescue-request.created` | New request created | `requestId`, `data` (current implementation publishes the full persisted master item, including internal storage fields) |
| `rescue-request.status-changed` | Any state transition | `requestId`, `previousStatus`, `newStatus`, `eventId`, `version` |
| `rescue-request.citizen-updated` | Citizen submits an update, or staff PATCH edits the master record | Citizen update: `requestId`, `updateId`, `updateType`, `updatePayload`, `createdAt`; PATCH: `requestId`, `updateId="patch"`, `updateType="PATCH"`, `updatePayload` |
| `rescue-request.priority-score-updated` | Staff priority sync API updates `priorityScore` | `requestId`, `previousPriorityScore`, `newPriorityScore`, optional `priorityLevel`, optional `note`, optional `updatedAt` |
| `rescue-request.resolved` | Request resolved | `requestId`, `eventId` |
| `rescue-request.cancelled` | Request cancelled | `requestId`, `eventId`, `reason` |

> **Note:** Event publishing is non-blocking — a failure to publish does **not** cause the
> HTTP request to fail.

### Prioritization Result Ingest

This service does not publish outbound prioritization commands or re-evaluation topics.
Instead, it consumes evaluated results from Rescue Prioritization Service through one shared SQS queue:

- queue: `rescue-prioritization-evaluated-{stage}`
- DLQ: `rescue-prioritization-evaluated-dlq-{stage}`

The shared queue can subscribe to two external SNS topics:

- `rescue.prioritization.created.v1`
- `rescue.prioritization.updated.v1`

Optional stack parameters:

- `PrioritizationCreatedTopicArn`
- `PrioritizationUpdatedTopicArn`

If either topic ARN is supplied, the stack creates the SNS-to-SQS subscription automatically.

Canonical inbound `messageType` on both result topics is `RescueRequestEvaluatedEvent`.
For transition compatibility, `RescueRequestReEvaluateEvent` is also accepted on
`rescue.prioritization.updated.v1` only.

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
- `body.submittedAt`
- `body.lastEvaluatedAt`
- `body.description`
- `body.location.latitude`
- `body.location.longitude`
- `body.peopleCount`

Validation rules:

- `incidentId` and `evaluateId` must be valid UUIDs
- `priorityScore` must be a decimal between `0` and `1`
- `priorityLevel` must be one of `LOW`, `NORMAL`, `HIGH`, `CRITICAL`
- `location` must be present with numeric `latitude` and `longitude`
- `correlationId` must match `CURRENT_STATE.latestPrioritySourceEventId`

That correlation target comes from the latest service-owned source event published on
`rescue-request-events-v1-{stage}`:

- `rescue-request.created`
- `rescue-request.citizen-updated`

When an evaluated message is accepted, the request `currentState` is updated with:

- `priorityScore`
- `priorityLevel`
- `status` (`SUBMITTED` requests move to `TRIAGED`; later non-terminal states are preserved)
- `latestPriorityEvaluationId`
- `latestPriorityReason`
- `latestPriorityEvaluatedAt`
- `latestPriorityCorrelationId`
- `lastPriorityIngestedAt`

Terminal requests are acknowledged and skipped. Result idempotency is keyed by `evaluateId`.

### Incident Catalog Sync

Incident data is synced from IncidentTracking Service into a dedicated local table:

- Trigger: Amazon EventBridge schedule every 30 minutes
- Lambda timeout: 30 seconds
- External HTTP timeout: 30 seconds
- Secret source: AWS Secrets Manager secret `rescue-request-service/incident-tracking/{stage}`
- Required secret keys: `apiUrl`, `apiKey`
- Optional secret keys: `accept`, `transactionIdHeader`

`GET /incidents` reads only from the local table, so client reads remain available even if
the upstream sync fails or times out.

---

## 11. Idempotency

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

## 12. Duplicate Detection

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

## 13. Internal Endpoints

### 13.1 GET /internal/incidents/catalog

Returns every row currently stored in `IncidentCatalogTable` for internal tooling/support use.

This endpoint returns the service's narrow internal shape and includes both:
- the five hardmock seed rows (`IncidentA` through `IncidentE`)
- any additional incidents synced from IncidentTracking Service

#### Response `200 OK`

```json
{
  "items": [
    {
      "incident_id": "MOCK-INC-001",
      "incident_type": "flood",
      "incident_name": "IncidentA",
      "status": "REPORTED",
      "incident_description": "Mock flood incident for internal testing and UI bootstrap"
    },
    {
      "incident_id": "019C774D-1AC5-758B-AE95-5CD4AEB89258",
      "incident_type": "fire",
      "incident_name": "IncidentF",
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
