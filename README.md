# 🛟 Rescue Request Service

Backend service for disaster rescue request management built with Python, AWS Lambda, DynamoDB, and SNS.

## 📌 Overview

**Rescue Request Service** is the central hub for receiving and managing rescue requests during disasters. It handles request intake, tracking code issuance, status management through a defined state machine, and publishes domain events for downstream services.

### Architecture
- **AWS API Gateway** - REST API (synchronous)
- **AWS Lambda** - Business logic
- **Amazon DynamoDB** - Persistence (single-table design)
- **Amazon SNS** - Async domain events
- **AWS SAM / CloudFormation** - Infrastructure as Code

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- AWS SAM CLI
- AWS CLI

### Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Run Unit Tests
```bash
make test-unit
# or
python -m pytest tests/unit/ -v
```

### Local Development
```bash
# Start DynamoDB Local
make local-db-start

# Start API (requires SAM CLI)
sam local start-api --template-file template.local.yaml --docker-network rescue-net

# Stop
make local-stop
```

### Deploy
```bash
# Dev
make deploy-dev

# Prod
make deploy-prod
```

## 📋 API Endpoints (17 total)

### Public (Citizens)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/rescue-requests` | Create rescue request |
| POST | `/v1/citizen/tracking/lookup` | Lookup by phone + tracking code |
| GET | `/v1/citizen/rescue-requests/{requestId}/status` | Get status |
| POST | `/v1/citizen/rescue-requests/{requestId}/updates` | Submit update |
| GET | `/v1/citizen/rescue-requests/{requestId}/updates` | List updates |

### Staff
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/rescue-requests/{requestId}` | Get request details |
| PATCH | `/v1/rescue-requests/{requestId}` | Patch request |
| GET | `/v1/rescue-requests/{requestId}/events` | List status events |
| POST | `/v1/rescue-requests/{requestId}/events` | Append status event |
| GET | `/v1/rescue-requests/{requestId}/current` | Get current state |
| GET | `/v1/incidents/{incidentId}/rescue-requests` | List by incident |
| GET | `/v1/idempotency-keys/{idempotencyKeyHash}` | Get idempotency record |

### Commands (State Machine)
| Method | Path | Transition |
|--------|------|------------|
| POST | `/v1/rescue-requests/{requestId}:triage` | SUBMITTED → TRIAGED |
| POST | `/v1/rescue-requests/{requestId}:assign` | TRIAGED → ASSIGNED |
| POST | `/v1/rescue-requests/{requestId}:start` | ASSIGNED → IN_PROGRESS |
| POST | `/v1/rescue-requests/{requestId}:resolve` | IN_PROGRESS → RESOLVED |
| POST | `/v1/rescue-requests/{requestId}:cancel` | * → CANCELLED |

## 🔄 State Machine

```
SUBMITTED → TRIAGED → ASSIGNED → IN_PROGRESS → RESOLVED
    |           |          |           |
    └───────────┴──────────┴───────────┴──→ CANCELLED
```

- **ASSIGNED** requires `responderUnitId`
- **CANCELLED** requires `reason`
- **RESOLVED** and **CANCELLED** are terminal states

## 🔑 Idempotency

- Use `X-Idempotency-Key` header (UUID) for command endpoints
- Same key + same payload → replay original response
- Same key + different payload → 409 Conflict
- TTL: 24 hours

## 📡 Async Events (SNS)

| Event | Trigger |
|-------|---------|
| `rescue-request.created` | New request |
| `rescue-request.status-changed` | Status transition |
| `rescue-request.citizen-updated` | Citizen update |
| `rescue-request.cancelled` | Request cancelled |
| `rescue-request.resolved` | Request resolved |

## 🏗 Project Structure

```
src/
├── handlers/          # Lambda handlers (thin)
│   ├── public/        # Citizen-facing
│   ├── staff/         # Staff-facing
│   └── commands/      # State machine commands
├── application/
│   ├── usecases/      # One operation per file
│   └── services/      # Idempotency, duplicate detection, transitions
├── domain/
│   ├── entities/      # Data models
│   ├── enums/         # Status, types
│   ├── rules/         # Business rules
│   └── events/        # Domain events
├── adapters/
│   ├── persistence/   # DynamoDB repositories
│   ├── messaging/     # SNS publisher
│   ├── auth/          # Auth stub (prepared for future)
│   └── utils/         # Phone normalizer, hashing, geohash
└── shared/            # Config, errors, response, validators
```

## 🧪 Testing

```bash
# Unit tests (no external deps)
make test-unit

# Integration tests (requires DynamoDB Local)
make local-db-start
make test-integration
```

## 🛠 Developer Info
- **Author:** Phattharaphum Kingchai
- **Student ID:** 6609612160