# API Summary

## Base Path: /v1

## Public Endpoints (Citizens)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | /v1/rescue-requests | CreateRescueRequest | Create new rescue request |
| POST | /v1/citizen/tracking/lookup | CitizenTrackingLookup | Lookup request by phone + tracking code |
| GET | /v1/citizen/rescue-requests/{requestId}/status | GetCitizenStatus | Get current status summary |
| POST | /v1/citizen/rescue-requests/{requestId}/updates | CreateCitizenUpdate | Submit additional info |
| GET | /v1/citizen/rescue-requests/{requestId}/updates | ListCitizenUpdates | List citizen updates |

## Staff Endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | /v1/rescue-requests/{requestId} | GetRescueRequest | Get full request details |
| PATCH | /v1/rescue-requests/{requestId} | PatchRescueRequest | Update request details |
| GET | /v1/rescue-requests/{requestId}/events | ListStatusEvents | List status event timeline |
| POST | /v1/rescue-requests/{requestId}/events | AppendStatusEvent | Append status event |
| GET | /v1/rescue-requests/{requestId}/current | GetCurrentState | Get current state |
| GET | /v1/incidents/{incidentId}/rescue-requests | ListByIncident | List requests by incident |
| GET | /v1/idempotency-keys/{idempotencyKeyHash} | GetIdempotencyRecord | Get idempotency key record |

## Command Endpoints (State Machine)

| Method | Path | Transition | Description |
|--------|------|------------|-------------|
| POST | /v1/rescue-requests/{requestId}:triage | SUBMITTED -> TRIAGED | Triage request |
| POST | /v1/rescue-requests/{requestId}:assign | TRIAGED -> ASSIGNED | Assign responder unit |
| POST | /v1/rescue-requests/{requestId}:start | ASSIGNED -> IN_PROGRESS | Start rescue operation |
| POST | /v1/rescue-requests/{requestId}:resolve | IN_PROGRESS -> RESOLVED | Resolve request |
| POST | /v1/rescue-requests/{requestId}:cancel | * -> CANCELLED | Cancel request |

## State Machine

```
SUBMITTED -> TRIAGED -> ASSIGNED -> IN_PROGRESS -> RESOLVED
    |           |          |             |
    +---------->+--------->+------------>+-------> CANCELLED
```

## Async Events (SNS)

Topic: `rescue-request-events.v1`

| Event Type | Published On |
|------------|-------------|
| rescue-request.created | New request created |
| rescue-request.status-changed | Any status transition |
| rescue-request.citizen-updated | Citizen submits update |
| rescue-request.cancelled | Request cancelled (terminal) |
| rescue-request.resolved | Request resolved (terminal) |

## Idempotency

- Use `X-Idempotency-Key` header (UUID format) for command endpoints
- Same key + same payload = replay original response
- Same key + different payload = 409 Conflict
- Key TTL: 24 hours

## Error Response Format

```json
{
  "message": "Human readable error message",
  "traceId": "uuid",
  "details": [
    { "field": "fieldName", "issue": "problem description" }
  ]
}
```
