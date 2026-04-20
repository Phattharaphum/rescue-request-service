# Health Check Endpoints

This document describes the service health-check endpoints and their expected behavior.

## Endpoints

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /v1/health`

## Probe Semantics

### `GET /v1/health/live` (Liveness)

- Purpose: verify the process/runtime is alive.
- Dependency checks: none.
- Expected status code:
  - `200` when process is alive.

### `GET /v1/health/ready` (Readiness)

- Purpose: verify the service is ready to serve API traffic.
- Critical dependency checks:
  - `RescueRequestTable`
  - `IdempotencyTable`
  - `IncidentCatalogTable`
- Expected status code:
  - `200` when all checks pass.
  - `503` when any dependency check fails.

### `GET /v1/health` (Summary)

- Purpose: combined liveness + readiness result in one response.
- Expected status code:
  - `200` when readiness is pass.
  - `503` when readiness is fail.

## Response Shape

### Liveness (`/v1/health/live`)

```json
{
  "service": "rescue-request-service",
  "stage": "dev",
  "region": "ap-southeast-2",
  "status": "pass",
  "timestamp": "2026-04-20T10:10:00+00:00",
  "checks": {
    "process": {
      "status": "pass",
      "uptimeMs": 15342
    }
  }
}
```

### Readiness (`/v1/health/ready`)

```json
{
  "service": "rescue-request-service",
  "stage": "dev",
  "region": "ap-southeast-2",
  "status": "pass",
  "timestamp": "2026-04-20T10:10:00+00:00",
  "checks": {
    "dynamodb": {
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

### Summary (`/v1/health`)

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
      "tables": []
    }
  }
}
```

## Operational Guidance

- Use `/v1/health/live` for restart decisions.
- Use `/v1/health/ready` for traffic gating (load balancer target health/readiness probe).
- Use `/v1/health` for dashboards and external monitors that need one endpoint.
