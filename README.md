# Rescue Request Service

Backend service for disaster rescue request management built with Python, AWS Lambda, DynamoDB, and SNS.

## Overview

Rescue Request Service receives rescue requests, manages state transitions, stores data in DynamoDB, and publishes domain events via SNS.

## Architecture

- AWS API Gateway (REST API)
- AWS Lambda (business logic)
- Amazon DynamoDB (single-table design)
- Amazon SNS (async domain events)
- AWS SAM / CloudFormation (IaC)

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- AWS CLI
- AWS SAM CLI

## Install

### bash
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### PowerShell
```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Local Development

### 1) Start local dependencies

### bash
```bash
make local-db-start
```

### PowerShell
```powershell
make local-db-start
```

This starts `dynamodb-local` on `http://localhost:8000` and creates required tables.

### 2) Start API

### bash
```bash
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

### PowerShell
```powershell
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

### 3) Stop local dependencies

### bash
```bash
make local-stop
```

### PowerShell
```powershell
make local-stop
```

## Tests

### Unit tests

```bash
make test-unit
```

### Integration tests

```bash
make test-integration
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

- `POST /v1/rescue-requests/{requestId}/triage`
- `POST /v1/rescue-requests/{requestId}/assign`
- `POST /v1/rescue-requests/{requestId}/start`
- `POST /v1/rescue-requests/{requestId}/resolve`
- `POST /v1/rescue-requests/{requestId}/cancel`

## Deploy via CloudFormation Console

This project uses SAM template, so deploy flow is: `build` -> `package` -> upload `packaged.yaml` to CloudFormation.

### 1) Build artifacts

### bash
```bash
sam build --template-file template.yaml --use-container
```

### PowerShell
```powershell
sam build --template-file template.yaml --use-container
```

### 2) Package artifacts to S3

Use **bucket name** only (not ARN).

### bash
```bash
sam package \
  --template-file .aws-sam/build/template.yaml \
  --s3-bucket <your-artifact-bucket-name> \
  --output-template-file packaged.yaml \
  --region ap-southeast-2
```

### PowerShell
```powershell
sam package `
  --template-file .aws-sam/build/template.yaml `
  --s3-bucket <your-artifact-bucket-name> `
  --output-template-file packaged.yaml `
  --region ap-southeast-2
```

### 3) Create/Update stack in CloudFormation console

1. Open CloudFormation Console
2. Click `Create stack` (or `Update stack`)
3. Choose `Upload a template file`
4. Upload `packaged.yaml`
5. Set parameter `Stage` (`dev` or `prod`)
6. Acknowledge IAM capability when prompted
7. Deploy stack

### 4) Verify outputs

After stack is `CREATE_COMPLETE` / `UPDATE_COMPLETE`, check outputs:
- `ApiEndpoint`
- `RescueRequestTableName`
- `IdempotencyTableName`
- `SnsTopicArn`

## Notes

- API Gateway REST API does not support command paths like `{requestId}:assign`; use `{requestId}/assign` format.
- If `sam package` shows `File with same data already exists ... skipping upload`, that is normal.
