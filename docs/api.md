# API Documentation

## Base path

All endpoints are relative to the API Gateway stage URL, e.g.:
`https://{api-id}.execute-api.{region}.amazonaws.com/{stage}`

---

## Endpoints

### POST /v1/requests

Create a new rescue request.

**Request body**

```json
{
  "incidentId": "string (required)",
  "requesterName": "string (required)",
  "description": "string (required)",
  "location": "string (required)"
}
```

**Responses**

| Status | Description |
|---|---|
| 201 | Request created. Returns full `RescueRequest` object. |
| 200 | Idempotent duplicate — same `idempotencyKey` already exists; returns existing request. |
| 400 | Bad Request — missing or malformed fields. |
| 409 | Conflict — weak duplicate detected (same `incidentId` + `requesterName` within 5 min). |
| 422 | Unprocessable Entity — `incidentId` not found in Incident Service. |
| 500 | Internal Server Error. |

---

### GET /v1/requests/{id}

Retrieve a rescue request by its ID.

**Path parameters**

| Name | Type | Description |
|---|---|---|
| id | string | The `requestId` of the rescue request |

**Responses**

| Status | Description |
|---|---|
| 200 | Returns full `RescueRequest` object. |
| 404 | Not Found. |
| 500 | Internal Server Error. |

---

### GET /v1/requests?incidentId=...

Search rescue requests by `incidentId`.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| incidentId | string | Filter requests by incidentId |

**Responses**

| Status | Description |
|---|---|
| 200 | Returns array of `RescueRequest` objects (may be empty). |
| 400 | Bad Request — missing `incidentId` query parameter. |
| 500 | Internal Server Error. |

---

### PATCH /v1/requests/{id}/status

Update the status of a rescue request with optimistic locking.

**Path parameters**

| Name | Type | Description |
|---|---|---|
| id | string | The `requestId` of the rescue request |

**Request body**

```json
{
  "status": "DISPATCHED | RESOLVED | CANCELLED",
  "reason": "string (optional)",
  "version": 1
}
```

`version` must match the current version stored in DynamoDB (optimistic locking).

**Responses**

| Status | Description |
|---|---|
| 200 | Returns updated `RescueRequest` object. |
| 400 | Bad Request — missing or invalid fields. |
| 404 | Not Found. |
| 409 | Conflict — `version` mismatch (optimistic lock failure) or invalid status transition. |
| 500 | Internal Server Error. |

---

## Error response format

```json
{
  "code": "NOT_FOUND",
  "message": "Rescue request abc123 not found"
}
```

## RescueRequest object

```json
{
  "requestId": "uuid",
  "incidentId": "string",
  "requesterName": "string",
  "description": "string",
  "location": "string",
  "status": "PENDING | DISPATCHED | RESOLVED | CANCELLED",
  "version": 1,
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "idempotencyKey": "string"
}
```
