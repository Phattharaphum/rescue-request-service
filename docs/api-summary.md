# API Reference

**Base URL:** `https://{apiId}.execute-api.{region}.amazonaws.com/{stage}/v1`

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
7. [Staff Endpoints](#7-staff-endpoints)
   - [GET /rescue-requests/{requestId}](#71-get-rescue-requestsrequestid)
   - [PATCH /rescue-requests/{requestId}](#72-patch-rescue-requestsrequestid)
   - [GET /rescue-requests/{requestId}/events](#73-get-rescue-requestsrequestidevents)
   - [POST /rescue-requests/{requestId}/events](#74-post-rescue-requestsrequestidevents)
   - [GET /rescue-requests/{requestId}/current](#75-get-rescue-requestsrequestidcurrent)
   - [GET /incidents/{incidentId}/rescue-requests](#76-get-incidentsincidentidrescue-requests)
   - [GET /idempotency-keys/{idempotencyKeyHash}](#77-get-idempotency-keysidempotencykeyhash)
8. [Command Endpoints (State Machine)](#8-command-endpoints-state-machine)
   - [POST /rescue-requests/{requestId}:triage](#81-post-rescue-requestsrequestidtriage)
   - [POST /rescue-requests/{requestId}:assign](#82-post-rescue-requestsrequestidassign)
   - [POST /rescue-requests/{requestId}:start](#83-post-rescue-requestsrequestidstart)
   - [POST /rescue-requests/{requestId}:resolve](#84-post-rescue-requestsrequestidresolve)
   - [POST /rescue-requests/{requestId}:cancel](#85-post-rescue-requestsrequestidcancel)
9. [State Machine](#9-state-machine)
10. [Async Events (SNS)](#10-async-events-sns)
11. [Idempotency](#11-idempotency)
12. [Duplicate Detection](#12-duplicate-detection)

---

## 1. Overview

The Rescue Request Service provides a REST API for managing disaster rescue requests.

| API Group | Audience | Auth Required |
|-----------|----------|---------------|
| **Public** | Citizens | No |
| **Staff** | Emergency-response staff | No (prepared for future) |
| **Commands** | Staff — state-machine transitions | No (prepared for future) |

---

## 2. Common Headers

| Header | Direction | Description |
|--------|-----------|-------------|
| `X-Idempotency-Key` | Request | UUID v4. Makes mutating operations safe to retry. Optional on all mutating endpoints. |
| `If-Match` | Request | Current `stateVersion` integer. Used for optimistic concurrency control on write operations. Returns `409` on mismatch. |
| `X-Forwarded-For` | Request | Client IP, set automatically by API Gateway. |
| `User-Agent` | Request | Client user-agent string. |
| `X-Trace-Id` | Response | UUID included in every response for request tracing. |

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
  "traceId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "details": [
    { "field": "contactPhone", "issue": "must be a valid phone number (10-15 digits)" }
  ]
}
```

| HTTP Status | Error Code | When |
|-------------|------------|------|
| `400` | `BAD_REQUEST` | Malformed request |
| `401` | `UNAUTHORIZED` | Missing or invalid credentials |
| `403` | `FORBIDDEN` | Phone + tracking code combination is invalid |
| `404` | `NOT_FOUND` | Resource does not exist |
| `409` | `CONFLICT` | Invalid state transition / version mismatch / duplicate / idempotency key reused with different payload |
| `422` | `VALIDATION_ERROR` | Input validation failure (see `details`) |
| `429` | `TOO_MANY_REQUESTS` | Rate limit exceeded |
| `500` | `INTERNAL_ERROR` | Unexpected server error |
| `503` | `SERVICE_UNAVAILABLE` | Downstream dependency unavailable |

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

**Duplicate detection** — a `409 Conflict` is returned if a request with the same
incident, phone, request type, approximate location, and submission time (within a
15-minute window) already exists and no idempotency key was supplied.

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
| Body | `contactPhone` | string (10–15 digits) | **Yes** | Contact phone number |
| Body | `sourceChannel` | SourceChannel | **Yes** | Submission channel |
| Body | `specialNeeds` | string \| null | No | Medical/mobility requirements |
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
  "trackingCode": "ABCD-1234",
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

**Error responses:** `409` (duplicate), `422` (validation)

---

### 6.2 POST /citizen/tracking/lookup

Looks up a rescue request using the citizen's phone number and tracking code.

#### Request Body

```json
{
  "contactPhone": "0812345678",
  "trackingCode": "ABCD-1234"
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

**Error responses:** `403` (phone/code combination invalid), `422` (missing fields)

---

### 6.3 GET /citizen/rescue-requests/{requestId}/status

Returns a simplified, citizen-facing status summary for a rescue request.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `requestId` | UUID | Rescue request identifier |

#### Response `200 OK`

```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ASSIGNED",
  "priorityLevel": "HIGH",
  "assignedUnitId": "UNIT-007",
  "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00",
  "stateVersion": 3
}
```

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | UUID | |
| `status` | RequestStatus | Current lifecycle status |
| `priorityLevel` | string \| null | Human-readable priority label |
| `assignedUnitId` | string \| null | Responding unit, if assigned |
| `lastUpdatedAt` | ISO-8601 \| null | Last state change timestamp |
| `stateVersion` | integer | Monotonically increasing version counter |

**Error responses:** `404`

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
| Body | `updateType` | UpdateType | **Yes** | Category of update |
| Body | `updatePayload` | object | **Yes** | Update-specific payload (see [UpdateType](#updatetype)) |

**Example request body:**
```json
{
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

**Error responses:** `404`, `409` (terminal state), `422`

---

### 6.5 GET /citizen/rescue-requests/{requestId}/updates

Returns a paginated list of all citizen-submitted updates for a rescue request.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `since` | ISO-8601 | — | Only return updates after this timestamp |

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

---

## 7. Staff Endpoints

### 7.1 GET /rescue-requests/{requestId}

Retrieves the master record and current state of a rescue request.
Optionally embeds the status-event history and/or citizen-submitted updates.

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
    "priorityScore": 85.5,
    "priorityLevel": "HIGH",
    "assignedUnitId": "UNIT-007",
    "assignedAt": "2024-01-15T11:00:00.000000+00:00",
    "latestNote": "Team dispatched, ETA 15 minutes",
    "lastUpdatedBy": "dispatcher-01",
    "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00"
  }
}
```

When `includeEvents=true` an `"events"` array is added.
When `includeCitizenUpdates=true` a `"citizenUpdates"` array is added.

**Error responses:** `404`

---

### 7.2 PATCH /rescue-requests/{requestId}

Partially updates the master record of a rescue request.

**Allowed fields:** `description`, `peopleCount`, `specialNeeds`, `locationDetails`, `addressLine`

**Forbidden fields:** `incidentId`, `status`, `requestId` — returning these in the body causes `422`.

Cannot be called when the request is in a terminal state.

#### Request

| Location | Field | Type | Required | Description |
|----------|-------|------|----------|-------------|
| Path | `requestId` | UUID | **Yes** | |
| Header | `X-Idempotency-Key` | UUID | No | Idempotency key |
| Header | `If-Match` | integer | No | Expected `stateVersion` for optimistic locking |
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

**Error responses:** `404`, `409` (terminal state or version mismatch), `422`

---

### 7.3 GET /rescue-requests/{requestId}/events

Returns a paginated list of status-change events for a rescue request.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `sinceVersion` | integer | — | Only return events with version > this value |
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
      "priorityScore": 75.0,
      "responderUnitId": null,
      "version": 2,
      "occurredAt": "2024-01-15T10:35:00.000000+00:00"
    }
  ],
  "nextCursor": null
}
```

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
| Body | `changeReason` | string \| null | No | Free-text reason |
| Body | `responderUnitId` | string \| null | No | Required when `newStatus=ASSIGNED` |
| Body | `reason` | string \| null | No | Required when `newStatus=CANCELLED` |
| Body | `priorityScore` | number \| null | No | Numerical priority score |
| Body | `priorityLevel` | string \| null | No | Human-readable priority label |
| Body | `note` | string \| null | No | Operational note |
| Body | `meta` | object \| null | No | Arbitrary additional metadata |

**Example request body:**
```json
{
  "newStatus": "TRIAGED",
  "changedBy": "staff-001",
  "changedByRole": "dispatcher",
  "changeReason": "Request verified, forwarding to field team"
}
```

#### Response `200 OK` — [StatusTransitionResponse](#statustransitionresponse)

**Error responses:** `404`, `409`, `422`

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
  "priorityScore": 85.5,
  "priorityLevel": "HIGH",
  "assignedUnitId": "UNIT-007",
  "assignedAt": "2024-01-15T11:00:00.000000+00:00",
  "latestNote": "Team dispatched, ETA 15 minutes",
  "lastUpdatedBy": "staff-001",
  "lastUpdatedAt": "2024-01-15T11:00:00.000000+00:00"
}
```

**Error responses:** `404`

---

### 7.6 GET /incidents/{incidentId}/rescue-requests

Returns a paginated list of rescue request summaries for the given incident.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results (1–100) |
| `cursor` | string | — | Pagination cursor |
| `status` | RequestStatus | — | Filter by status |

#### Response `200 OK`

```json
{
  "items": [
    {
      "requestId": "550e8400-e29b-41d4-a716-446655440000",
      "incidentId": "INC-2024-001",
      "status": "ASSIGNED",
      "requestType": "FLOOD",
      "contactName": "Somchai Jaidee",
      "submittedAt": "2024-01-15T10:30:00.000000+00:00"
    }
  ],
  "nextCursor": null
}
```

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

## 8. Command Endpoints (State Machine)

All command endpoints share the same response shape ([StatusTransitionResponse](#statustransitionresponse))
and accept the same optional headers (`X-Idempotency-Key`, `If-Match`).

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

### 8.1 POST /rescue-requests/{requestId}:triage

`SUBMITTED → TRIAGED`

#### Request Body (optional)

| Field | Type | Description |
|-------|------|-------------|
| `changedBy` | string | Staff identifier (default: `"staff"`) |
| `changedByRole` | string | Staff role (default: `"staff"`) |
| `priorityScore` | number \| null | Numerical priority |
| `priorityLevel` | string \| null | Human-readable priority label |
| `note` | string \| null | Operational note |
| `meta` | object \| null | Additional metadata |

**Error responses:** `404`, `409`

---

### 8.2 POST /rescue-requests/{requestId}:assign

`TRIAGED → ASSIGNED`

**`responderUnitId` is required.**

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `responderUnitId` | string | **Yes** | Responding unit identifier |
| `changedBy` | string | No | Staff identifier |
| `changedByRole` | string | No | Staff role |
| `priorityScore` | number \| null | No | |
| `priorityLevel` | string \| null | No | |
| `note` | string \| null | No | |
| `meta` | object \| null | No | |

**Error responses:** `404`, `409`, `422`

---

### 8.3 POST /rescue-requests/{requestId}:start

`ASSIGNED → IN_PROGRESS`

#### Request Body (optional)

Same optional fields as [triage](#81-post-rescue-requestsrequestidtriage).

**Error responses:** `404`, `409`

---

### 8.4 POST /rescue-requests/{requestId}:resolve

`IN_PROGRESS → RESOLVED` *(terminal)*

Publishes `rescue-request.status-changed` and `rescue-request.resolved` SNS events.

#### Request Body (optional)

Same optional fields as [triage](#81-post-rescue-requestsrequestidtriage).

**Error responses:** `404`, `409`

---

### 8.5 POST /rescue-requests/{requestId}:cancel

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

**Error responses:** `404`, `409`, `422`

---

## 9. State Machine

```
SUBMITTED ──:triage──▶ TRIAGED ──:assign──▶ ASSIGNED ──:start──▶ IN_PROGRESS ──:resolve──▶ RESOLVED
    │                     │                     │                      │
    └──────────────────────┴─────────────────────┴──────────────────────┴──:cancel──▶ CANCELLED
```

### Allowed Transitions

| From | To | Command |
|------|----|---------|
| `SUBMITTED` | `TRIAGED` | `:triage` |
| `TRIAGED` | `ASSIGNED` | `:assign` |
| `ASSIGNED` | `IN_PROGRESS` | `:start` |
| `IN_PROGRESS` | `RESOLVED` | `:resolve` |
| `SUBMITTED` | `CANCELLED` | `:cancel` |
| `TRIAGED` | `CANCELLED` | `:cancel` |
| `ASSIGNED` | `CANCELLED` | `:cancel` |
| `IN_PROGRESS` | `CANCELLED` | `:cancel` |

Attempting an invalid transition returns `409 Conflict`.
Attempting to transition from a terminal state (`RESOLVED` or `CANCELLED`) also returns `409 Conflict`.

### Required Fields per Transition

| Target Status | Required Field |
|---------------|---------------|
| `ASSIGNED` | `responderUnitId` |
| `CANCELLED` | `reason` |

---

## 10. Async Events (SNS)

**Topic:** `rescue-request-events-v1-{stage}`

All events are wrapped in the following envelope:

```json
{
  "metadata": {
    "eventType": "rescue-request.status-changed",
    "eventId": "uuid",
    "timestamp": "2024-01-15T10:35:00.000000+00:00",
    "partitionKey": "550e8400-e29b-41d4-a716-446655440000",
    "schemaVersion": "1.0",
    "source": "rescue-request-service",
    "correlationId": "optional-trace-id"
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
| `rescue-request.created` | New request created | `requestId`, `data` (master record) |
| `rescue-request.status-changed` | Any state transition | `requestId`, `previousStatus`, `newStatus`, `eventId`, `version` |
| `rescue-request.citizen-updated` | Citizen submits an update | `requestId`, `updateId`, `updateType` |
| `rescue-request.resolved` | Request resolved | `requestId`, `eventId` |
| `rescue-request.cancelled` | Request cancelled | `requestId`, `eventId`, `reason` |

> **Note:** Event publishing is non-blocking — a failure to publish does **not** cause the
> HTTP request to fail.

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
| `POST /rescue-requests/{requestId}/events` | `AppendStatusEvent` |
| `POST /rescue-requests/{requestId}:triage` | `Triage` |
| `POST /rescue-requests/{requestId}:assign` | `Assign` |
| `POST /rescue-requests/{requestId}:start` | `Start` |
| `POST /rescue-requests/{requestId}:resolve` | `Resolve` |
| `POST /rescue-requests/{requestId}:cancel` | `Cancel` |

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

`timeBucket` divides submissions into **15-minute windows** so that a citizen can submit
a new request for the same situation once the window expires.

If a matching signature is found the service returns `409 Conflict` with the ID of the
existing request.

> Duplicate detection is **bypassed** when an `X-Idempotency-Key` header is present.
> Idempotent retries are always safe.
