# Dependency Mapping

## rescue-request-service

### Internal Infrastructure

| Dependency | Type | Purpose |
|---|---|---|
| Amazon DynamoDB | AWS Managed | Persistent storage for rescue requests |
| Amazon SNS | AWS Managed | Event publishing |
| Amazon API Gateway | AWS Managed | REST API exposure |
| Amazon SQS (DLQ) | AWS Managed | Dead-letter queue for failed Lambda invocations |

---

### DynamoDB Table

- **Table Name**: `rescue-requests` (configurable via `DYNAMODB_TABLE_NAME`)
- **Primary Key**: `requestId` (String, Hash Key)
- **GSI**: `incidentId-index` — partition key `incidentId` for querying all requests tied to an incident
- **Attributes stored**: `requestId`, `incidentId`, `requesterName`, `description`, `location`, `status`, `version`, `createdAt`, `updatedAt`, `idempotencyKey`

---

### SNS Topics

| Topic | ARN env var | Event type |
|---|---|---|
| rescue-request-created | `SNS_TOPIC_ARN_CREATED` | `rescue.request.created.v1` |
| rescue-request-status-changed | `SNS_TOPIC_ARN_STATUS_CHANGED` | `rescue.request.status-changed.v1` |

---

### External Services

#### Incident Service (HTTP)

- **Base URL**: `INCIDENT_SERVICE_URL` (e.g. `http://incident-service/`)
- **Purpose**: Validates that the referenced `incidentId` exists before accepting a new rescue request
- **Timeout**: Configurable via `INCIDENT_SERVICE_TIMEOUT_MS` (default 3000 ms)
- **Retry**: 1 automatic retry on network error
- **Failure behaviour**: Returns `422 Unprocessable Entity` if the incident cannot be confirmed

---

### API Gateway

- **Type**: REST API (regional)
- **Stage**: `{Stage}` parameter (`dev`, `prod`)
- **Resources**:
  - `POST /v1/requests`
  - `GET /v1/requests`
  - `GET /v1/requests/{id}`
  - `PATCH /v1/requests/{id}/status`
