# Events Documentation

## Overview

The rescue-request-service publishes events to Amazon SNS. Each message body is a JSON-encoded envelope with a `payload` object containing the event-specific data.

---

## rescue.request.created.v1

Published when a new rescue request is successfully created.

**SNS Topic**: `rescue-request-created`  
**Event type**: `rescue.request.created.v1`

### Envelope

```json
{
  "eventId": "uuid",
  "eventType": "rescue.request.created.v1",
  "version": "1",
  "timestamp": "ISO-8601",
  "payload": {
    "requestId": "uuid",
    "incidentId": "string",
    "requesterName": "string",
    "status": "PENDING",
    "createdAt": "ISO-8601"
  }
}
```

### Field descriptions

| Field | Type | Description |
|---|---|---|
| eventId | uuid | Unique identifier for this event occurrence |
| eventType | string | Always `rescue.request.created.v1` |
| version | string | Schema version — currently `"1"` |
| timestamp | ISO-8601 | When the event was emitted |
| payload.requestId | uuid | The newly created rescue request ID |
| payload.incidentId | string | The associated incident ID |
| payload.requesterName | string | Name of the person who made the request |
| payload.status | string | Always `PENDING` at creation |
| payload.createdAt | ISO-8601 | Timestamp of record creation |

---

## rescue.request.status-changed.v1

Published when the status of a rescue request is updated.

**SNS Topic**: `rescue-request-status-changed`  
**Event type**: `rescue.request.status-changed.v1`

### Envelope

```json
{
  "eventId": "uuid",
  "eventType": "rescue.request.status-changed.v1",
  "version": "1",
  "timestamp": "ISO-8601",
  "payload": {
    "requestId": "uuid",
    "previousStatus": "PENDING",
    "newStatus": "DISPATCHED",
    "reason": "string | null",
    "changedAt": "ISO-8601"
  }
}
```

### Field descriptions

| Field | Type | Description |
|---|---|---|
| eventId | uuid | Unique identifier for this event occurrence |
| eventType | string | Always `rescue.request.status-changed.v1` |
| version | string | Schema version — currently `"1"` |
| timestamp | ISO-8601 | When the event was emitted |
| payload.requestId | uuid | The rescue request that changed |
| payload.previousStatus | string | Status before the transition |
| payload.newStatus | string | Status after the transition |
| payload.reason | string or null | Optional reason supplied by the caller |
| payload.changedAt | ISO-8601 | Timestamp of the status change |

---

## Versioning policy

- `v1` is the current stable version of all events.
- Non-breaking additions (new optional fields) do **not** increment the version.
- Breaking changes (removed fields, type changes, renamed fields) **must** bump the version to `v2` and run both versions in parallel during the transition period.
- Consumers must tolerate unknown additional fields (forward-compatible).
