# Synchronous Function Contract (Code-Verified)

Last verified against source code: 2026-05-16

This document is the API contract for all API Gateway synchronous HTTP routes defined in `template.yaml`.
It is derived from actual handlers/use-cases/repositories under `src/`.

## 1) Scope

Included:
- All `/v1/...` API Gateway routes in `template.yaml`.

Excluded:
- Scheduled jobs (`SyncIncidentCatalogFunction`, `StreamPollerFunction`).
- SQS ingestion handlers.
- Lambda Function URL stream endpoint.

## 2) Runtime Conventions

### 2.1 Base path
- Base path is `/v1`.

### 2.2 Response headers
Every API response includes:
- `Content-Type: application/json`
- `X-Trace-Id: <uuid>`
- `Vary: Origin`
- `Access-Control-Allow-Origin`

Origin behavior:
- If request `Origin` is in allow-list (`https://rescue-request.phatphum.me`, `http://localhost:3000`), response reflects that origin.
- Otherwise it returns the first configured origin.

### 2.3 Error envelope
All handled errors follow this JSON shape:

```json
{
  "message": "Human-readable error",
  "errorCode": "BAD_REQUEST|VALIDATION_ERROR|UNAUTHORIZED|FORBIDDEN|NOT_FOUND|CONFLICT|SERVICE_UNAVAILABLE|INTERNAL_ERROR",
  "traceId": "uuid",
  "requestId": "api-gateway-request-id-or-null",
  "timestamp": "ISO-8601",
  "path": "/v1/...",
  "method": "GET|POST|PATCH|DELETE",
  "details": []
}
```

Notes:
- `X-Trace-Id` response header equals `traceId` in the error body.
- `details` is always present (possibly empty).

### 2.4 JSON body parsing
For endpoints that parse request body:
- Invalid JSON -> `400 BAD_REQUEST`
- JSON not an object (for example array/string) -> `400 BAD_REQUEST`

### 2.5 Pagination
List endpoints use:
- `limit` default `20`, allowed `1..100`
- `cursor` opaque base64 token (`nextCursor` from previous page)

If `cursor` is malformed, it is silently ignored (first page behavior), not a `400`.

## 3) Route Inventory

### 3.1 Public
- `GET /v1/health`
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/rescue-requests`
- `GET /v1/incidents`
- `POST /v1/citizen/tracking/lookup`
- `GET /v1/citizen/rescue-requests/{requestId}/status`
- `POST /v1/citizen/rescue-requests/{requestId}/updates`
- `GET /v1/citizen/rescue-requests/{requestId}/updates`

### 3.2 Staff
- `GET /v1/rescue-requests/{requestId}`
- `PATCH /v1/rescue-requests/{requestId}`
- `PATCH /v1/rescue-requests/{requestId}/priority`
- `GET /v1/rescue-requests/{requestId}/events`
- `POST /v1/rescue-requests/{requestId}/events`
- `GET /v1/rescue-requests/{requestId}/current`
- `GET /v1/incidents/{incidentId}/rescue-requests`
- `GET /v1/idempotency-keys/{idempotencyKeyHash}`

### 3.3 Command
- `POST /v1/rescue-requests/{requestId}/triage`
- `POST /v1/rescue-requests/{requestId}/assign`
- `POST /v1/rescue-requests/{requestId}/start`
- `POST /v1/rescue-requests/{requestId}/resolve`
- `POST /v1/rescue-requests/{requestId}/cancel`

### 3.4 Internal (api-key protected)
- `GET /v1/internal/incidents/catalog`
- `DELETE /v1/internal/incidents/catalog`
- `DELETE /v1/internal/incidents/catalog/with-requests`
- `DELETE /v1/internal/rescue-requests/orphaned`
- `DELETE /v1/internal/rescue-requests`
- `DELETE /v1/internal/maintenance/all`

## 4) Endpoint Contracts

## 4.1 Health endpoints

### GET `/v1/health/live`
- Purpose: liveness.
- Success: `200`.
- Response shape:

```json
{
  "service": "rescue-request-service",
  "stage": "dev|prod|local",
  "region": "ap-southeast-1",
  "status": "pass",
  "timestamp": "ISO-8601",
  "checks": {
    "process": {
      "status": "pass",
      "uptimeMs": 12345
    }
  }
}
```

### GET `/v1/health/ready`
- Purpose: readiness (DynamoDB table describe checks).
- Success: `200` when all checked tables are `ACTIVE`.
- Failure: `503` when any table check fails.
- Tables checked:
- `RescueRequestTable`
- `IdempotencyTable`
- `IncidentCatalogTable`

### GET `/v1/health`
- Purpose: combined summary (`liveness` + `readiness`).
- Success: `200` when readiness is pass.
- Failure: `503` when readiness is fail.

## 4.2 POST `/v1/rescue-requests`

ชื่อฟังก์ชัน: `CreateRescueRequest`

สร้างคำร้องขอความช่วยเหลือใหม่จาก citizen/public channel และออก tracking code 6 หลักสำหรับติดตามสถานะหรือส่งข้อมูลเพิ่มเติมภายหลัง

### HTTP contract

Method:
- `POST`

Path:
- `/v1/rescue-requests`

Path parameters:
- ไม่มี

Query parameters:
- ไม่มี

Headers:
- `Content-Type: application/json` recommended; handler currently does not enforce this header.
- `Accept: application/json` optional; response is always JSON.
- `X-Idempotency-Key` optional but strongly recommended for client retry. Current code does not validate UUID format.
- `X-Forwarded-For` optional; stored on idempotency record when idempotency is used.
- `User-Agent` optional; stored on idempotency record when idempotency is used.
- `X-Client-Id` is not currently read by this handler.

### Request body

Current implementation expects a flat JSON object. It does not accept the older nested `location` / `contact` shape for this endpoint.

Required fields:

| Field | Type | Rule |
|---|---|---|
| `incidentId` | string | Must exist in `IncidentCatalogTable`; handler does not UUID-validate this value. |
| `requestType` | string enum | One of `MEDICAL`, `EVACUATION`, `SUPPLY`. |
| `description` | string | Required, non-empty. |
| `peopleCount` | integer-compatible | Must be integer `>= 1` and fit DynamoDB number precision. |
| `latitude` | number-compatible | Finite number in `[-90, 90]`. |
| `longitude` | number-compatible | Finite number in `[-180, 180]`. |
| `contactName` | string | Required, non-empty. |
| `contactPhone` | string | Must match `^[\d\+\-\s\(\)]{7,20}$`; normalized internally for hashing/lookup. |
| `sourceChannel` | string enum | One of `WEB`, `MOBILE`, `LINE`, `PHONE`, `WALK_IN`, `OTHER`. |

Optional fields:
- `specialNeeds`
- `locationDetails`
- `province`
- `district`
- `subdistrict`
- `addressLine`

Example request:

```json
{
  "incidentId": "8b9b6d5b-7d5e-4d0b-a7e2-2a0a6bd5c111",
  "requestType": "EVACUATION",
  "description": "ติดอยู่ชั้น 2 ต้องการอพยพออกจากพื้นที่น้ำท่วม",
  "peopleCount": 4,
  "specialNeeds": ["bedridden"],
  "latitude": 18.7883,
  "longitude": 98.9853,
  "locationDetails": { "floor": "2", "landmark": "หน้าโรงเรียน" },
  "province": "เชียงใหม่",
  "district": "เมืองเชียงใหม่",
  "subdistrict": "สุเทพ",
  "addressLine": "123 ม.2 ถ.ห้วยแก้ว",
  "contactName": "สมชาย",
  "contactPhone": "0812345678",
  "sourceChannel": "MOBILE"
}
```

### Processing behavior

- Generates `requestId` as UUID v4.
- Generates `trackingCode` as 6-digit plain text and returns it only in the create response.
- Stores only `trackingCodeHash` in DynamoDB, not the plain tracking code.
- Normalizes `contactPhone` for hashing. Thai `+66...` / `66...` formats are normalized to leading `0...`.
- Writes `MASTER`, `CURRENT_STATE`, initial `STATUS_EVENT`, `TRACKING_LOOKUP`, `PHONE_UNIQUE`, `INCIDENT_PROJECTION`, and `DUPLICATE_SIGNATURE` items.
- Initial status is `SUBMITTED` with `stateVersion=1`.
- Publishes `rescue-request.created` to SNS best-effort after persistence. Publish failure is logged and does not fail the create response.

Business conflicts:
- A normalized phone number can have only one existing request in the current implementation.
- If `X-Idempotency-Key` is not provided, duplicate-signature detection is applied using `incidentId`, normalized phone, `requestType`, geohash precision 7, and a 5-minute time bucket.

### Success response

Status:
- `201 Created`

Headers:
- Standard response headers only: `Content-Type`, `X-Trace-Id`, `Vary`, `Access-Control-Allow-Origin`.
- Current implementation does not return `Location`.
- Current implementation does not return `Idempotency-Replayed`.

Body:

```json
{
  "requestId": "3f9fd8e4-23b7-4ed7-9f0e-4e2f78274b8a",
  "trackingCode": "493027",
  "status": "SUBMITTED",
  "submittedAt": "2026-02-21T10:30:00+00:00"
}
```

Notes:
- `requestId` is a UUID string, not `REQ-8812-9901`.
- `trackingCode` is returned as top-level field, not nested under `tracking`.
- `submittedAt` is produced by Python `datetime.isoformat()` and currently uses `+00:00` UTC offset format, not always `Z`.

### Idempotency behavior

- `X-Idempotency-Key` is optional but recommended for retries.
- Idempotency scope is `CreateRescueRequest` + `POST:/v1/rescue-requests`.
- Same scoped key and same canonical request body returns the stored response.
- Same scoped key with a different request body returns `409 CONFLICT`.
- Idempotency lock timeout is 5 minutes.
- Idempotency record TTL is 24 hours.
- Replayed create response is still returned by the handler as `201 Created`, not `200 OK`.
- Current handler does not expose a replay indicator header.

Errors:
- `400` invalid JSON/object body.
- `409` duplicate phone, duplicate signature, idempotency payload mismatch, idempotency in-progress, transaction conflict.
- `422` validation errors, including missing required fields, invalid enum values, invalid phone format, invalid coordinates, invalid `peopleCount`, or unknown `incidentId`.
- `500` unhandled internal/dependency errors.

Example duplicate response:

```json
{
  "message": "Duplicate request detected",
  "errorCode": "CONFLICT",
  "traceId": "0c7f6d5e-55b1-4f4e-9e58-1d9b0a2c91bb",
  "requestId": "api-gateway-request-id-or-null",
  "timestamp": "2026-02-21T10:30:05+00:00",
  "path": "/v1/rescue-requests",
  "method": "POST",
  "details": [
    {
      "field": "request",
      "issue": "existing request: 3f9fd8e4-23b7-4ed7-9f0e-4e2f78274b8a"
    }
  ]
}
```

### Dependency, reliability, and failure handling

Dependencies:
- DynamoDB `RescueRequestTable-{stage}`
- DynamoDB `IdempotencyTable-{stage}` when `X-Idempotency-Key` is supplied
- DynamoDB `IncidentCatalogTable-{stage}`
- SNS topic `rescue-request-events-v1-{stage}` best-effort after successful persistence

Synchronous external service calls:
- None. Incident validity is checked against the local incident catalog table, not by calling Incident Service synchronously.

Retry guidance:
- Clients may retry, but should reuse the same `X-Idempotency-Key` and exactly the same request body.
- If the first request succeeded but the response was lost, replay returns the original body while the idempotency record is retained.

Current implementation notes:
- No endpoint-level authorization is enforced for this public create route.
- No explicit rate limiting is implemented in the handler.
- Dependency exceptions from DynamoDB/SNS are not all normalized to `503`; persistence failures may surface as `500` unless mapped by application code.

## 4.3 GET `/v1/incidents`

Query:
- `limit` optional, default `20`, range `1..100`.
- `cursor` optional.
- `status` optional exact-match filter on stored incident status.

Success:
- `200 OK`

```json
{
  "items": [
    {
      "incidentId": "string",
      "incidentType": "string|null",
      "incidentName": "string|null",
      "incidentSequence": 1,
      "status": "string|null",
      "incidentDescription": "string|null"
    }
  ],
  "nextCursor": "string|null"
}
```

Notes:
- `catalogPartition` and `catalogSortKey` are removed from output.

Errors:
- `400` invalid `limit`.

## 4.4 POST `/v1/citizen/tracking/lookup`

Body:
- `contactPhone` required.
- `trackingCode` required.

Success:
- `200 OK`

```json
{
  "requestId": "uuid",
  "incidentId": "string"
}
```

Errors:
- `400` invalid JSON/object body.
- `403` phone/code combination not found.
- `422` required field validation.

## 4.5 GET `/v1/citizen/rescue-requests/{requestId}/status`

Path:
- `requestId` required UUID.

Success:
- `200 OK`

```json
{
  "requestId": "uuid",
  "incidentId": "string",
  "requestType": "MEDICAL|EVACUATION|SUPPLY",
  "status": "SUBMITTED|TRIAGED|ASSIGNED|IN_PROGRESS|RESOLVED|CANCELLED",
  "statusMessage": "string|null",
  "nextSuggestedAction": "string|null",
  "description": "string|null",
  "peopleCount": 1,
  "specialNeeds": "any",
  "submittedAt": "ISO-8601|null",
  "lastCitizenUpdateAt": "ISO-8601|null",
  "contactName": "string|null",
  "contactPhoneMasked": "string|null",
  "location": {
    "latitude": 0,
    "longitude": 0,
    "locationDetails": "string|null",
    "addressLine": "string|null",
    "province": "string|null",
    "district": "string|null",
    "subdistrict": "string|null"
  },
  "priorityLevel": "string|null",
  "assignedUnitId": "string|null",
  "assignedAt": "ISO-8601|null",
  "latestNote": "string|null",
  "lastUpdatedAt": "ISO-8601|null",
  "stateVersion": 1,
  "latestEvent": {
    "eventId": "uuid",
    "version": 1,
    "previousStatus": "string|null",
    "newStatus": "string",
    "occurredAt": "ISO-8601",
    "changeReason": "string|null",
    "meta": {},
    "priorityScore": 0.8,
    "responderUnitId": "string|null"
  },
  "recentEvents": []
}
```

Notes:
- `recentEvents` contains up to 5 newest events.
- `latestEvent` is selected from `recentEvents` matching current `stateVersion` when available.
- This endpoint currently does not require tracking code/auth.

Errors:
- `400` invalid/missing UUID path parameter.
- `404` request not found.

## 4.6 POST `/v1/citizen/rescue-requests/{requestId}/updates`

Path:
- `requestId` required UUID.

Headers:
- `X-Idempotency-Key` optional.

Body required fields:
- `updateType`
- `updatePayload`
- `trackingCode`

`updateType` enum:
- `NOTE`
- `LOCATION_DETAILS`
- `PEOPLE_COUNT`
- `SPECIAL_NEEDS`
- `CONTACT_INFO`

`updatePayload` rules:
- `NOTE` -> requires non-empty `note`.
- `LOCATION_DETAILS` -> requires non-empty `locationDetails`.
- `PEOPLE_COUNT` -> requires integer `peopleCount >= 1`.
- `SPECIAL_NEEDS` -> requires non-empty `specialNeeds`.
- `CONTACT_INFO` -> requires at least one of non-empty `contactPhone` or `contactName`; if `contactPhone` provided, phone format is validated.

Business rules:
- Tracking code hash must match request master record.
- Terminal requests (`RESOLVED`, `CANCELLED`) cannot be updated.

Success:
- `201 Created`

```json
{
  "updateId": "uuid",
  "requestId": "uuid",
  "updateType": "NOTE|LOCATION_DETAILS|PEOPLE_COUNT|SPECIAL_NEEDS|CONTACT_INFO",
  "createdAt": "ISO-8601"
}
```

Errors:
- `400` invalid JSON/object body or invalid UUID path.
- `403` invalid tracking code.
- `404` request not found.
- `409` terminal state conflict, idempotency conflict.
- `422` validation errors.

Replay behavior:
- Replayed response is returned as `201` by handler.

## 4.7 GET `/v1/citizen/rescue-requests/{requestId}/updates`

Path:
- `requestId` required UUID.

Query:
- `limit` optional, default `20`, range `1..100`.
- `cursor` optional.
- `since` optional ISO-8601 datetime.

Success:
- `200 OK`

```json
{
  "items": [
    {
      "updateId": "uuid",
      "requestId": "uuid",
      "updateType": "string",
      "updatePayload": {},
      "citizenAuthMethod": "tracking_code",
      "createdAt": "ISO-8601"
    }
  ],
  "nextCursor": "string|null"
}
```

Errors:
- `400` invalid UUID path, `limit`, or `since` format.
- `404` request not found.

## 4.8 GET `/v1/rescue-requests/{requestId}`

Path:
- `requestId` required UUID.

Query:
- `includeEvents` optional (`true` enables `events` array).
- `includeCitizenUpdates` optional (`true` adds `citizenUpdates` alias).

Success:
- `200 OK`

```json
{
  "master": {},
  "currentState": {},
  "updateItems": [],
  "events": [],
  "citizenUpdates": []
}
```

Field behavior:
- `master` = all master attributes except `PK`, `SK`, `itemType`.
- `currentState` = current-state attributes excluding hidden internal fields.
- `updateItems` is always present (up to 100 latest by storage order).
- `citizenUpdates` appears only when `includeCitizenUpdates=true` and is same content as `updateItems`.
- `events` appears only when `includeEvents=true` (up to 100 events).

Errors:
- `400` invalid/missing UUID path.
- `404` master not found.

## 4.9 PATCH `/v1/rescue-requests/{requestId}`

Path:
- `requestId` required UUID.

Headers:
- `X-Idempotency-Key` optional.
- `If-Match` optional integer >= 1 (parsed, but not enforced by current repository implementation for this endpoint).

Allowed body fields:
- `description`
- `peopleCount`
- `specialNeeds`
- `locationDetails`
- `addressLine`

Forbidden fields:
- `incidentId`
- `status`
- `requestId`

Rules:
- At least one allowed field must be present.
- Terminal requests cannot be patched.

Success:
- `200 OK`

```json
{
  "requestId": "uuid",
  "updated": ["description", "peopleCount"]
}
```

Errors:
- `400` invalid JSON/object body, invalid UUID path, invalid `If-Match`.
- `404` request not found.
- `409` terminal state conflict, idempotency conflict.
- `422` forbidden fields or no valid fields.

## 4.10 PATCH `/v1/rescue-requests/{requestId}/priority`

Path:
- `requestId` required UUID.

Headers:
- `X-Idempotency-Key` optional.
- `If-Match` optional integer >= 1, enforced against `stateVersion` when provided.

Allowed body fields only:
- `priorityScore` number in `[0,1]` or `null`
- `priorityLevel` non-empty string or `null`
- `note` non-empty string or `null`

Rules:
- At least one of above fields required.
- Unsupported extra fields are rejected.
- Terminal requests cannot be updated.

Success:
- `200 OK`

```json
{
  "requestId": "uuid",
  "priorityScore": 0.9,
  "priorityLevel": "CRITICAL",
  "note": "Escalated",
  "updatedAt": "ISO-8601",
  "updated": ["priorityScore", "priorityLevel", "note"]
}
```

Errors:
- `400` invalid JSON/object body, invalid UUID path, invalid `If-Match`.
- `404` request not found.
- `409` terminal state conflict, version mismatch, idempotency conflict.
- `422` unsupported fields / invalid value constraints.

## 4.11 GET `/v1/rescue-requests/{requestId}/events`

Path:
- `requestId` required UUID.

Query:
- `limit` optional, default `20`, range `1..100`.
- `cursor` optional.
- `sinceVersion` optional integer >= 0.
- `order` optional `ASC|DESC`, default `ASC`.

Success:
- `200 OK`

```json
{
  "items": [
    {
      "eventId": "uuid",
      "requestId": "uuid",
      "previousStatus": "string|null",
      "newStatus": "string",
      "changedBy": "string",
      "changedByRole": "string",
      "changeReason": "string|null",
      "meta": {},
      "priorityScore": 0.8,
      "responderUnitId": "string|null",
      "version": 2,
      "occurredAt": "ISO-8601"
    }
  ],
  "nextCursor": "string|null"
}
```

Notes:
- Missing request does not raise `404`; it returns an empty list.

Errors:
- `400` invalid UUID path, `limit`, `sinceVersion`, or `order`.

## 4.12 POST `/v1/rescue-requests/{requestId}/events`

Generic staff transition endpoint.

Path:
- `requestId` required UUID.

Headers:
- `X-Idempotency-Key` optional.
- `If-Match` optional integer >= 1, enforced.

Body required:
- `newStatus`
- `changedBy`
- `changedByRole`

Transition/field rules:
- `newStatus` must be valid `RequestStatus`.
- Transition must follow allowed state machine.
- `newStatus=ASSIGNED` requires `responderUnitId`.
- `newStatus=CANCELLED` requires `reason`.
- Optional `priorityScore` must be numeric and within `[0,1]`.

Success:
- `200 OK`

```json
{
  "eventId": "uuid",
  "requestId": "uuid",
  "previousStatus": "SUBMITTED",
  "newStatus": "TRIAGED",
  "version": 2,
  "occurredAt": "ISO-8601"
}
```

Errors:
- `400` invalid JSON/object body, invalid UUID path, invalid `If-Match`.
- `404` request not found.
- `409` terminal transition, invalid transition, version mismatch, concurrency conflict, idempotency conflict.
- `422` missing required body fields or transition requirement validation.

## 4.13 GET `/v1/rescue-requests/{requestId}/current`

Path:
- `requestId` required UUID.

Success:
- `200 OK`
- Returns cleaned current state object.

Typical fields:
- `requestId`, `incidentId`, `status`, `stateVersion`, `lastEventId`
- `priorityScore`, `priorityLevel`
- `assignedUnitId`, `assignedAt`, `latestNote`
- `lastUpdatedBy`, `lastUpdatedAt`
- Optional async-ingestion fields such as `latestPriorityEvaluationId`, `latestMissionId`, `latestMissionStatus`, etc.

Errors:
- `400` invalid/missing UUID path.
- `404` request not found.

## 4.14 GET `/v1/incidents/{incidentId}/rescue-requests`

Path:
- `incidentId` required non-empty string (not UUID-validated).

Query:
- `limit` optional, default `20`, range `1..100`.
- `cursor` optional.
- `status` optional, must be one of `SUBMITTED|TRIAGED|ASSIGNED|IN_PROGRESS|RESOLVED|CANCELLED`.

Success:
- `200 OK`

```json
{
  "items": [
    {
      "requestId": "uuid",
      "incidentId": "string",
      "status": "string",
      "currentState": {}
    }
  ],
  "nextCursor": "string|null"
}
```

Notes:
- Service merges incident projection + master + currentState per item.
- `status` filter is applied after merge; result count may be less than `limit`.

Errors:
- `400` missing path parameter, invalid `limit`, invalid `status` value.

## 4.15 GET `/v1/idempotency-keys/{idempotencyKeyHash}`

Path:
- `idempotencyKeyHash` required non-empty string.
- No pattern validation is applied.

Query:
- `includeResponse` optional boolean (`true`/other).
- `includeRequestFingerprint` optional boolean.

Success:
- `200 OK`

Default response:

```json
{
  "idempotencyKeyHash": "string",
  "operationName": "string",
  "status": "IN_PROGRESS|COMPLETED|FAILED",
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "resultResourceId": "string|null"
}
```

When `includeResponse=true`, adds:
- `responseStatusCode`
- `responseBody` (stored string payload)

When `includeRequestFingerprint=true`, adds:
- `requestFingerprint`

Errors:
- `400` missing path parameter.
- `404` record not found.

## 4.16 Command endpoints

Routes:
- `POST /v1/rescue-requests/{requestId}/triage`
- `POST /v1/rescue-requests/{requestId}/assign`
- `POST /v1/rescue-requests/{requestId}/start`
- `POST /v1/rescue-requests/{requestId}/resolve`
- `POST /v1/rescue-requests/{requestId}/cancel`

Common behavior:
- `requestId` must be UUID.
- Body is optional object; if fields are missing:
- `changedBy` defaults to `"staff"`
- `changedByRole` defaults to `"staff"`
- `X-Idempotency-Key` optional.
- `If-Match` optional integer >= 1 and enforced when provided.
- Success always `200 OK` with transition summary:

```json
{
  "eventId": "uuid",
  "requestId": "uuid",
  "previousStatus": "string",
  "newStatus": "string",
  "version": 2,
  "occurredAt": "ISO-8601"
}
```

Per-route transition target:
- `triage` -> `TRIAGED`
- `assign` -> `ASSIGNED`
- `start` -> `IN_PROGRESS`
- `resolve` -> `RESOLVED`
- `cancel` -> `CANCELLED`

Required by transition rules:
- `ASSIGNED` requires `responderUnitId`.
- `CANCELLED` requires `reason`.

Allowed state transitions:
- `SUBMITTED -> TRIAGED|ASSIGNED|CANCELLED`
- `TRIAGED -> ASSIGNED|CANCELLED`
- `ASSIGNED -> IN_PROGRESS|CANCELLED`
- `IN_PROGRESS -> RESOLVED|CANCELLED`
- `RESOLVED` and `CANCELLED` are terminal.

Errors:
- `400` invalid JSON/object body, invalid UUID path, invalid `If-Match`.
- `404` request not found.
- `409` invalid/terminal transition, version mismatch, concurrency conflict, idempotency conflict.
- `422` transition requirement validation (for example missing `responderUnitId` or `reason`).

## 4.17 GET `/v1/internal/incidents/catalog`

Auth:
- Requires header `api-key` exactly matching `INTERNAL_API_KEY`.
- Missing/invalid key -> `401`.
- Missing server configuration `INTERNAL_API_KEY` -> `503`.

Success:
- `200 OK`

```json
{
  "items": [
    {
      "incident_id": "string",
      "incident_type": "string|null",
      "incident_name": "string|null",
      "status": "string|null",
      "incident_description": "string|null"
    }
  ]
}
```

Notes:
- Items are sorted by `incidentSequence` then `incidentId`.

## 4.18 Internal maintenance DELETE endpoints

Auth:
- Requires `api-key` (same rules as above).

Supported routes:
- `DELETE /v1/internal/incidents/catalog`
- `DELETE /v1/internal/incidents/catalog/with-requests`
- `DELETE /v1/internal/rescue-requests/orphaned`
- `DELETE /v1/internal/rescue-requests`
- `DELETE /v1/internal/maintenance/all`

Unsupported method/route:
- `400 BAD_REQUEST` with message `Unsupported internal maintenance method` or `Unsupported internal maintenance route`.

Success:
- `200 OK`

Response shapes:

`DELETE /v1/internal/incidents/catalog`

```json
{
  "operation": "clear_incident_catalog",
  "deletedIncidents": 0,
  "deletedRequestItems": 0
}
```

`DELETE /v1/internal/incidents/catalog/with-requests`

```json
{
  "operation": "clear_incident_catalog",
  "deletedIncidents": 0,
  "deletedRequestItems": 0
}
```

`DELETE /v1/internal/rescue-requests/orphaned`

```json
{
  "operation": "delete_orphaned_requests",
  "deletedRequests": 0,
  "deletedRequestItems": 0
}
```

`DELETE /v1/internal/rescue-requests`

```json
{
  "operation": "clear_requests",
  "deletedRequestItems": 0
}
```

`DELETE /v1/internal/maintenance/all`

```json
{
  "operation": "clear_all_data",
  "deletedIncidents": 0,
  "deletedRequestItems": 0
}
```

## 5) Idempotency (Implemented Behavior)

Supported endpoints:
- `POST /v1/rescue-requests` (`CreateRescueRequest`)
- `POST /v1/citizen/rescue-requests/{requestId}/updates` (`CreateCitizenUpdate`)
- `PATCH /v1/rescue-requests/{requestId}` (`PatchRescueRequest`)
- `PATCH /v1/rescue-requests/{requestId}/priority` (`UpdateRescueRequestPriority`)
- `POST /v1/rescue-requests/{requestId}/events` (`AppendStatusEvent`)
- Command endpoints: `Triage|Assign|Start|Resolve|Cancel`

Core behavior:
- Key scope is operation + resource scope, so same idempotency key can be reused across different endpoints/resources.
- Same scoped key + different payload -> `409 CONFLICT`.
- `IN_PROGRESS` lock timeout is 5 minutes.
- Record TTL is 24 hours.
- Reserve retries up to 3 attempts.

Replay behavior from handlers:
- Create and citizen-update handlers still return `201` on replay.
- Other supported handlers return `200` on replay.

## 6) Known Current-Behavior Notes (Important for Clients)

- Staff/public routes (except internal routes) currently have no authorization checks.
- `GET /v1/citizen/rescue-requests/{requestId}/status` does not require tracking-code authentication at handler/use-case level.
- `PATCH /v1/rescue-requests/{requestId}` accepts `If-Match` but does not currently enforce version matching in repository update.
- `GET /v1/idempotency-keys/{idempotencyKeyHash}` does not validate hash format; any non-empty string is accepted.
- Invalid pagination cursor is ignored (not rejected).

