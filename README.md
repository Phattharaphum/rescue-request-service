# Rescue Request Service

Backend service for disaster rescue request management built with Python, AWS Lambda, DynamoDB, SNS, and AWS SAM.

## Project Owner

- Name: Phattharaphum Kingchai
- StudentID: 6609612160

## Project Overview

This service provides a REST API for:
- creating rescue requests from citizens
- tracking request status
- updating request details
- managing staff workflows (`triage -> assign -> start -> resolve/cancel`)
- publishing domain events to SNS

## Useful Links

- [API Summary](./docs/api-summary.md): Human-readable API reference covering endpoints, behaviors, and integration notes.
- [DOCS](./DOCS.md): Project documentation and implementation details.
- [Data Model](./docs/data-model.md): Current DynamoDB table design, item types, and field-level persistence model.
- [Frontend Repository](https://github.com/Phattharaphum/rescue-request-service-frontend): First-party frontend codebase that consumes this backend service.
- [Frontend Application](Not available): Deployed web application for submitting and tracking rescue requests.

## Architecture

- API: AWS API Gateway (REST)
- Compute: AWS Lambda (Python 3.11)
- Database: DynamoDB (single-table design + idempotency table)
- Messaging: SNS
- IaC: AWS SAM / CloudFormation
- Local stack: LocalStack (DynamoDB + SNS + SQS)

## Project Structure

```text
rescue-request-service/
├─ docs/                     # OpenAPI spec and API summary
├─ events/                   # Sample event payloads for local testing
├─ infra/                    # Infra-related assets/scripts
├─ local/
│  ├─ docker-compose.yml     # LocalStack container setup
│  └─ dynamodb/
│     ├─ create_tables.sh    # DynamoDB table bootstrap (bash)
│     ├─ create_tables.ps1   # DynamoDB table bootstrap (PowerShell)
│     ├─ delete_tables.sh
│     └─ seed_data.py
├─ scripts/                  # Utility scripts
├─ src/
│  ├─ adapters/              # External integrations (DynamoDB/SNS/utils/auth)
│  ├─ application/           # Use cases and application services
│  ├─ domain/                # Domain models/rules
│  ├─ handlers/              # Lambda handlers (public/staff/commands)
│  └─ shared/                # Shared config/constants
├─ tests/
│  ├─ unit/
│  └─ integration/
├─ template.yaml             # Main SAM template (deploy)
├─ template.local.yaml       # SAM local template
├─ packaged.yaml             # Packaged template output for CloudFormation
└─ Makefile
```

## Prerequisites

- Python 3.11+
- Docker Desktop (with Docker Compose)
- AWS CLI v2
- AWS SAM CLI
- GNU Make

## Install Dependencies

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

## Local Configuration

Local runtime is aligned to LocalStack endpoint `4566`.

- `.env.example` (host-side defaults)
- `.env.json` (SAM local Lambda container env)
- `template.local.yaml` uses `DYNAMODB_ENDPOINT=http://localstack:4566`

Current `.env.json` format:

```json
{
  "Parameters": {
    "STAGE": "local",
    "APP_AWS_REGION": "ap-southeast-1",
    "AWS_REGION": "ap-southeast-1",
    "AWS_DEFAULT_REGION": "ap-southeast-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "DYNAMODB_ENDPOINT": "http://localstack:4566",
    "SNS_TOPIC_ARN": "arn:aws:sns:ap-southeast-1:000000000000:rescue-request-events-v1"
  }
}
```

## Local Setup (End-to-End)

### Step 1: Start LocalStack and create tables

### bash
```bash
make local-db-start
```

### PowerShell
```powershell
make local-db-start
```

What this does:
- starts `local/localstack` on `http://localhost:4566`
- creates `RescueRequestTable`
- creates `IdempotencyTable`

Verify tables were created:

### bash
```bash
aws dynamodb list-tables --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### PowerShell
```powershell
aws dynamodb list-tables --endpoint-url http://localhost:4566 --region ap-southeast-1
```

Expected table names:
- `RescueRequestTable`
- `IdempotencyTable`

### Step 2: Export AWS CLI credentials for LocalStack

### bash
```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=ap-southeast-1
```

### PowerShell
```powershell
$env:AWS_ACCESS_KEY_ID="test"
$env:AWS_SECRET_ACCESS_KEY="test"
$env:AWS_DEFAULT_REGION="ap-southeast-1"
```

### Step 3: Create SNS topic for local event publishing

### bash
```bash
aws sns create-topic \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --name rescue-request-events-v1
```

### PowerShell
```powershell
aws sns create-topic `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --name rescue-request-events-v1
```

### Step 4: Start API with SAM local

### bash
```bash
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

### PowerShell
```powershell
sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json
```

API base URL:
- `http://127.0.0.1:3000/v1`

### Step 5: Stop local environment

### bash
```bash
make local-stop
```

### PowerShell
```powershell
make local-stop
```

## Deploy to AWS (SAM Package + CloudFormation)

This section follows the exact flow: build -> package -> use `packaged.yaml` to deploy.

### Step 0: Prepare deployment resources

Create an S3 bucket in your target region (example `ap-southeast-2`) for deployment artifacts.

### bash
```bash
aws s3 mb s3://<s3-bucket> --region ap-southeast-2
```

### PowerShell
```powershell
aws s3 mb s3://<s3-bucket> --region ap-southeast-2
```

### Step 1: Set AWS credentials and region

### bash
```bash
export AWS_ACCESS_KEY_ID="xxxx"
export AWS_SECRET_ACCESS_KEY="xxxx"
export AWS_DEFAULT_REGION="xxxx"
```

### PowerShell
```powershell
$env:AWS_ACCESS_KEY_ID="xxxx"
$env:AWS_SECRET_ACCESS_KEY="xxxx"
$env:AWS_DEFAULT_REGION="xxxx"
```

### Step 2: Verify active AWS identity

### bash
```bash
aws sts get-caller-identity
```

### PowerShell
```powershell
aws sts get-caller-identity
```

### Step 3: Fix APPDATA path (Windows/SAM CLI compatibility)

### bash (Git Bash on Windows)
```bash
export APPDATA="$USERPROFILE/AppData/Roaming"
```

### PowerShell
```powershell
$env:APPDATA = "$env:USERPROFILE\AppData\Roaming"
```

### Step 4: Build application

### bash
```bash
sam build --template-file template.yaml --use-container
```

### PowerShell
```powershell
sam build --template-file template.yaml --use-container
```

### Step 5: Package template to S3

### bash
```bash
sam package \
  --template-file .aws-sam/build/template.yaml \
  --s3-bucket <s3 bucket> \
  --output-template-file packaged.yaml \
  --region ap-southeast-2
```

### PowerShell
```powershell
sam package `
  --template-file .aws-sam/build/template.yaml `
  --s3-bucket <s3 bucket> `
  --output-template-file packaged.yaml `
  --region ap-southeast-2
```

### Step 6: Deploy using `packaged.yaml` (CloudFormation)

Option A: deploy directly with CloudFormation CLI.

### bash
```bash
aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name rescue-request-service-dev \
  --capabilities CAPABILITY_IAM \
  --region ap-southeast-2
```

### PowerShell
```powershell
aws cloudformation deploy `
  --template-file packaged.yaml `
  --stack-name rescue-request-service-dev `
  --capabilities CAPABILITY_IAM `
  --region ap-southeast-2
```

Option B: deploy with SAM using the same packaged template.

### bash
```bash
sam deploy \
  --template-file packaged.yaml \
  --stack-name rescue-request-service-dev \
  --capabilities CAPABILITY_IAM \
  --region ap-southeast-2
```

### PowerShell
```powershell
sam deploy `
  --template-file packaged.yaml `
  --stack-name rescue-request-service-dev `
  --capabilities CAPABILITY_IAM `
  --region ap-southeast-2
```

### Step 7: Verify stack and outputs

### bash
```bash
aws cloudformation describe-stacks \
  --stack-name rescue-request-service-dev \
  --region ap-southeast-2
```

### PowerShell
```powershell
aws cloudformation describe-stacks `
  --stack-name rescue-request-service-dev `
  --region ap-southeast-2
```

## Quick API Smoke Test (Local)

### Create request

### bash
```bash
curl -X POST http://127.0.0.1:3000/v1/rescue-requests \
  -H "Content-Type: application/json" \
  -d '{
    "incidentId": "INC-001",
    "requestType": "MEDICAL",
    "description": "Need evacuation support",
    "peopleCount": 3,
    "latitude": 13.7563,
    "longitude": 100.5018,
    "contactName": "Somchai",
    "contactPhone": "0812345678",
    "sourceChannel": "WEB"
  }'
```

### PowerShell
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

## Verify SNS Publish Locally (Optional)

### bash
```bash
TOPIC_ARN=$(aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1 --query TopicArn --output text)
QUEUE_URL=$(aws sqs create-queue --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-debug --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url "$QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
aws sns subscribe --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn "$TOPIC_ARN" --protocol sqs --notification-endpoint "$QUEUE_ARN"
```

### PowerShell
```powershell
$topicArn = aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1 --query TopicArn --output text
$queueUrl = aws sqs create-queue --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-debug --query QueueUrl --output text
$queueArn = aws sqs get-queue-attributes --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url $queueUrl --attribute-names QueueArn --query Attributes.QueueArn --output text
aws sns subscribe --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn $topicArn --protocol sqs --notification-endpoint $queueArn
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
- `PATCH /v1/rescue-requests/{requestId}/priority`
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

## Troubleshooting

### Local Runtime

- If `sam local` cannot connect to DynamoDB, verify `.env.json` has `DYNAMODB_ENDPOINT=http://localstack:4566`.
- If API returns `ResourceNotFoundException: Cannot do operations on a non-existent table`:
  - run `make local-db-start`
  - run `aws dynamodb list-tables --endpoint-url http://localhost:4566 --region ap-southeast-1`
  - verify `APP_AWS_REGION` is set to the same region used when creating tables
  - confirm both `RescueRequestTable` and `IdempotencyTable` exist
- If API returns `SNS_TOPIC_ARN not set`, create topic in LocalStack and set ARN in `.env.json`.
- If Docker shows `Access is denied` on Windows, run Docker Desktop and terminal with sufficient permission.
- If `docker compose` warns `version is obsolete`, it is informational; deployment can still continue.

### Packaging and Deployment

- If `aws sts get-caller-identity` fails, check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`.
- If `sam build --use-container` fails:
  - ensure Docker is running
  - verify your account can access Docker daemon
- If `sam package` fails with S3 errors:
  - verify `<s3 bucket>` exists in `ap-southeast-2`
  - verify IAM user/role has `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`
- If CloudFormation deploy fails with capability error, include:
  - `--capabilities CAPABILITY_IAM`
- If CloudFormation stack is in rollback state:
  - inspect events:
    - bash:
      ```bash
      aws cloudformation describe-stack-events --stack-name rescue-request-service-dev --region ap-southeast-2
      ```
    - PowerShell:
      ```powershell
      aws cloudformation describe-stack-events --stack-name rescue-request-service-dev --region ap-southeast-2
      ```
- If `sam package` shows repeated `File with same data already exists`, this is normal for unchanged artifacts.
