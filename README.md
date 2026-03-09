# Rescue Request Service

Backend service for disaster rescue request management, built with Python, AWS Lambda, DynamoDB, and SNS.

## Overview

Rescue Request Service is the central API for receiving and managing rescue requests during disasters.

Main responsibilities:
- Receive rescue requests from citizens
- Manage request status transitions via state machine
- Handle idempotent writes for create/command operations
- Publish domain events to SNS for downstream services

## Tech Stack

- Python 3.11
- AWS SAM (Lambda + API Gateway)
- DynamoDB (single-table design)
- SNS (async domain events)
- LocalStack (local DynamoDB/SNS/SQS)

## Prerequisites

Install the following before setup:
- Python 3.11+
- Docker Desktop (with Docker Compose)
- AWS CLI v2
- AWS SAM CLI
- GNU Make (or run equivalent commands manually)

## Repository Setup

### 1) Clone and enter project

#### bash
```bash
git clone <your-repo-url>
cd rescue-request-service
```

#### PowerShell
```powershell
git clone <your-repo-url>
Set-Location rescue-request-service
```

### 2) Install dependencies

#### bash
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### PowerShell
```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Alternative:

#### bash
```bash
make install
```

#### PowerShell
```powershell
make install
```

## Environment Configuration

This project uses LocalStack locally.

### 1) Local env file

Use `.env.example` as reference. Required local values:

```env
AWS_REGION=ap-southeast-1
AWS_DEFAULT_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
DYNAMODB_ENDPOINT=http://localhost:4566
```

### 2) SAM local env overrides (`.env.json`)

`sam local` runs your Lambda in Docker, so endpoint must use Docker network service name (`localstack`) instead of `localhost`.

```json
{
  "Parameters": {
    "STAGE": "local",
    "AWS_REGION": "ap-southeast-1",
    "AWS_DEFAULT_REGION": "ap-southeast-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "DYNAMODB_ENDPOINT": "http://localstack:4566",
    "SNS_TOPIC_ARN": "arn:aws:sns:ap-southeast-1:000000000000:rescue-request-events-v1"
  }
}
```

## Local Development (Detailed)

### Step 1: Start LocalStack and create DynamoDB tables

#### bash
```bash
make local-db-start
```

#### PowerShell
```powershell
make local-db-start
```

This will:
- Start `localstack` from `local/docker-compose.yml`
- Enable `dynamodb,sns,sqs`
- Create `RescueRequestTable` and `IdempotencyTable`

### Step 2: Export local AWS variables for CLI commands

#### bash
```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=ap-southeast-1
```

#### PowerShell
```powershell
$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_DEFAULT_REGION = "ap-southeast-1"
```

### Step 3: Create SNS topic (required for event publish)

#### bash
```bash
aws sns create-topic \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --name rescue-request-events-v1
```

#### PowerShell
```powershell
aws sns create-topic `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --name rescue-request-events-v1
```

### Step 4: Start local API

#### bash
```bash
make local-start
```

#### PowerShell
```powershell
make local-start
```

Equivalent direct SAM command:

#### bash
```bash
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

#### PowerShell
```powershell
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

API default URL:
- `http://127.0.0.1:3000`

### Step 5: Stop local services

#### bash
```bash
make local-stop
```

#### PowerShell
```powershell
make local-stop
```

## Verify SNS Publish End-to-End

### Step 1: Create SQS queue and subscribe to SNS

#### bash
```bash
TOPIC_ARN=$(aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1 --query TopicArn --output text)
QUEUE_URL=$(aws sqs create-queue --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-debug --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url "$QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)

aws sns subscribe --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn "$TOPIC_ARN" --protocol sqs --notification-endpoint "$QUEUE_ARN"
```

#### PowerShell
```powershell
$topicArn = aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1 --query TopicArn --output text
$queueUrl = aws sqs create-queue --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-debug --query QueueUrl --output text
$queueArn = aws sqs get-queue-attributes --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url $queueUrl --attribute-names QueueArn --query Attributes.QueueArn --output text

aws sns subscribe --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn $topicArn --protocol sqs --notification-endpoint $queueArn
```

### Step 2: Send create rescue request

#### bash
```bash
curl -X POST http://127.0.0.1:3000/v1/rescue-requests \
  -H "Content-Type: application/json" \
  -d '{
    "incidentId":"INC-001",
    "requestType":"MEDICAL",
    "description":"Need evacuation support",
    "peopleCount":3,
    "latitude":13.7563,
    "longitude":100.5018,
    "contactName":"Somchai",
    "contactPhone":"0812345678",
    "sourceChannel":"WEB"
  }'
```

#### PowerShell
```powershell
$body = @{
  incidentId   = "INC-001"
  requestType  = "MEDICAL"
  description  = "Need evacuation support"
  peopleCount  = 3
  latitude     = 13.7563
  longitude    = 100.5018
  contactName  = "Somchai"
  contactPhone = "0812345678"
  sourceChannel = "WEB"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3000/v1/rescue-requests" -ContentType "application/json" -Body $body
```

### Step 3: Verify publish results

Expected in SAM log:
- `Published event rescue-request.created for <requestId>`

Receive message from SQS:

#### bash
```bash
aws sqs receive-message \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --queue-url "$QUEUE_URL" \
  --max-number-of-messages 10 \
  --wait-time-seconds 10 \
  --message-attribute-names All \
  --attribute-names All
```

#### PowerShell
```powershell
aws sqs receive-message `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --queue-url $queueUrl `
  --max-number-of-messages 10 `
  --wait-time-seconds 10 `
  --message-attribute-names All `
  --attribute-names All
```

## Testing

### Unit tests

#### bash
```bash
make test-unit
```

#### PowerShell
```powershell
make test-unit
```

### Integration tests

Requires LocalStack running.

#### bash
```bash
make local-db-start
make test-integration
```

#### PowerShell
```powershell
make local-db-start
make test-integration
```

## Build and Deploy

### Build

#### bash
```bash
make build
```

#### PowerShell
```powershell
make build
```

### Deploy

#### bash
```bash
make deploy-dev
make deploy-prod
```

#### PowerShell
```powershell
make deploy-dev
make deploy-prod
```

## API Endpoints

### Public

- `POST /v1/rescue-requests`
- `POST /v1/citizen/tracking/lookup`
- `GET /v1/citizen/rescue-requests/{requestId}/status`
- `POST /v1/citizen/rescue-requests/{requestId}/updates`
- `GET /v1/citizen/rescue-requests/{requestId}/updates`

### Staff

- `GET /v1/rescue-requests/{requestId}`
- `PATCH /v1/rescue-requests/{requestId}`
- `GET /v1/rescue-requests/{requestId}/events`
- `POST /v1/rescue-requests/{requestId}/events`
- `GET /v1/rescue-requests/{requestId}/current`
- `GET /v1/incidents/{incidentId}/rescue-requests`
- `GET /v1/idempotency-keys/{idempotencyKeyHash}`

### Commands

- `POST /v1/rescue-requests/{requestId}:triage`
- `POST /v1/rescue-requests/{requestId}:assign`
- `POST /v1/rescue-requests/{requestId}:start`
- `POST /v1/rescue-requests/{requestId}:resolve`
- `POST /v1/rescue-requests/{requestId}:cancel`

## State Machine

`SUBMITTED -> TRIAGED -> ASSIGNED -> IN_PROGRESS -> RESOLVED`

Rules:
- `CANCELLED` can be reached from non-terminal states
- `ASSIGNED` requires `responderUnitId`
- `CANCELLED` requires `reason`
- `RESOLVED` and `CANCELLED` are terminal

## Domain Events (SNS)

- `rescue-request.created`
- `rescue-request.status-changed`
- `rescue-request.citizen-updated`
- `rescue-request.cancelled`
- `rescue-request.resolved`

## Troubleshooting

- `SNS_TOPIC_ARN not set, skipping publish`: check `.env.json` and ensure topic exists in LocalStack
- `ResourceNotFoundException` for DynamoDB: ensure tables were created on `http://localhost:4566`
- PowerShell parser error with `\`: use one-line commands or PowerShell backtick (`` ` ``) for multiline
- Lambda cannot connect to LocalStack: inside SAM container endpoint must be `http://localstack:4566`

## Project Structure

```text
src/
  handlers/        # Lambda entrypoints
  application/     # Use cases and app services
  domain/          # Entities, enums, business rules
  adapters/        # DynamoDB, SNS, utils, auth adapter
  shared/          # Config, logger, errors, response helpers
local/
  docker-compose.yml
  dynamodb/
tests/
```
