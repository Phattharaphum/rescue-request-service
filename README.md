# Rescue Request Service

Backend service for disaster rescue request management built with Python, AWS Lambda, DynamoDB, SNS, SQS, and AWS SAM.

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
- ingesting prioritization results from SQS
- syncing incident catalog data from IncidentTracking Service

## Useful Links

- [API Summary](./docs/api-summary.md)
- [DOCS](./DOCS.md)
- [Data Model](./docs/data-model.md)
- [Prioritization + Incident Sync](./docs/prioritization-incident-sync.md)
- [Frontend Repository](https://github.com/Phattharaphum/rescue-request-service-frontend)

## Table of Contents

1. [Architecture](#architecture)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Install Dependencies](#install-dependencies)
5. [Local Configuration](#local-configuration)
6. [Local Setup (Core)](#local-setup-core)
7. [SNS/SQS Local Resources](#snssqs-local-resources)
8. [Inspect SNS/SQS Resources](#inspect-snssqs-resources)
9. [Subscribe Queue to Topic and Wait for Messages](#subscribe-queue-to-topic-and-wait-for-messages)
10. [Invoke Lambda Locally](#invoke-lambda-locally)
11. [Incident Catalog Sync Test Setup](#incident-catalog-sync-test-setup)
12. [Prioritization Result Ingest Test Setup](#prioritization-result-ingest-test-setup)
13. [Secrets Manager Commands (LocalStack)](#secrets-manager-commands-localstack)
14. [Local Validation and Deploy-Parity Checklist](#local-validation-and-deploy-parity-checklist)
15. [Deploy to AWS (SAM Package + CloudFormation)](#deploy-to-aws-sam-package--cloudformation)
16. [Quick API Smoke Test (Local)](#quick-api-smoke-test-local)
17. [Tests](#tests)
18. [API Endpoints](#api-endpoints)
19. [Troubleshooting](#troubleshooting)

## Architecture

- API: AWS API Gateway (REST)
- Compute: AWS Lambda (Python 3.11)
- Database: DynamoDB (`RescueRequestTable`, `IdempotencyTable`, `IncidentCatalogTable`)
- Messaging: SNS + SQS
- Secrets: AWS Secrets Manager (for IncidentTracking config)
- IaC: AWS SAM / CloudFormation
- Local runtime: SAM CLI + LocalStack

## Project Structure

```text
rescue-request-service/
|-- docs/
|-- events/
|-- infra/
|-- local/
|   |-- docker-compose.yml
|   |-- bootstrap/
|   |   `-- bootstrap_resources.ps1
|   `-- dynamodb/
|       |-- create_tables.sh
|       |-- create_tables.ps1
|       |-- reset_tables.ps1
|       `-- seed_data.py
|-- scripts/
|-- src/
|-- tests/
|-- template.yaml
|-- template.local.yaml
|-- packaged.yaml
`-- Makefile
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

Local runtime uses LocalStack endpoint `http://localhost:4566`.
LocalStack services enabled by `local/docker-compose.yml`:
- `dynamodb`
- `sns`
- `sqs`
- `secretsmanager`
- `events`
- `cloudwatch`
- `logs`

Files:
- `.env` for host-side defaults
- `.env.json` for `sam local` container environment
- `template.local.yaml` for local resource names and Lambda wiring

Current `.env.json` example:

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
    "SNS_TOPIC_ARN": "arn:aws:sns:ap-southeast-1:000000000000:rescue-request-events-v1",
    "INCIDENT_CATALOG_TABLE_NAME": "IncidentCatalogTable",
    "PRIORITIZATION_COMMANDS_TOPIC_ARN": "arn:aws:sns:ap-southeast-1:000000000000:rescue-prioritization-commands-v1",
    "PRIORITIZATION_REEVALUATE_TOPIC_ARN": "arn:aws:sns:ap-southeast-1:000000000000:rescue-prioritization-updated-v1",
    "INCIDENT_SYNC_SECRET_ID": "rescue-request-service/incident-tracking/local",
    "INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS": "30"
  }
}
```

## Local Setup (Core)

### Step 1: Start LocalStack and bootstrap local AWS resources

### bash

```bash
make local-db-start
```

### PowerShell

```powershell
make local-db-start
```

This starts LocalStack with enabled services:
- `dynamodb`, `sns`, `sqs`, `secretsmanager`, `events`, `cloudwatch`, `logs`

This also creates/updates DynamoDB tables:
- `RescueRequestTable`
- `IdempotencyTable`
- `IncidentCatalogTable`

This also bootstraps SNS/SQS resources and subscriptions:
- SNS topics: `rescue-request-events-v1`, `rescue-prioritization-created-v1`, `rescue-prioritization-updated-v1`
- SQS queues: `rescue-request-events-v1-stream`, `rescue-prioritization-evaluated`, `rescue-prioritization-evaluated-dlq`
- SNS subscriptions: `rescue-request-events-v1` -> `rescue-request-events-v1-stream`
- SNS subscriptions: `rescue-prioritization-created-v1` -> `rescue-prioritization-evaluated`
- SNS subscriptions: `rescue-prioritization-updated-v1` -> `rescue-prioritization-evaluated`

This also bootstraps Secrets Manager:
- `rescue-request-service/incident-tracking/local` (or value from `INCIDENT_SYNC_SECRET_ID`)

Optional: re-run only messaging + secrets bootstrap without recreating tables:

### bash

```bash
make local-bootstrap
```

### PowerShell

```powershell
make local-bootstrap
```

### Step 2: Export AWS credentials for LocalStack

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

### Step 3: Start API with SAM local

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

### Step 4: Stop local environment

### bash

```bash
make local-stop
```

### PowerShell

```powershell
make local-stop
```
## SNS/SQS Local Resources

### Resource names used by local vs deploy templates

| Purpose | Local name (`template.local.yaml`) | Deploy name (`template.yaml`) |
|---|---|---|
| Service-owned event topic | `rescue-request-events-v1` | `rescue-request-events-v1-{stage}` |
| Stream queue for service topic | `rescue-request-events-v1-stream` | `rescue-request-events-v1-stream-{stage}` |
| Prioritization evaluated queue | `rescue-prioritization-evaluated` | `rescue-prioritization-evaluated-{stage}` |
| Prioritization DLQ | `rescue-prioritization-evaluated-dlq` | `rescue-prioritization-evaluated-dlq-{stage}` |
| External prioritization created topic | `rescue-prioritization-created-v1` | external |
| External prioritization updated topic | `rescue-prioritization-updated-v1` | external |

### Manual create local SNS/SQS resources (optional)

`make local-db-start` already creates these resources automatically.
Use this section only when you need to recreate individual resources manually.

### bash

```bash
ENDPOINT=http://localhost:4566
REGION=ap-southeast-1

EVENTS_TOPIC_ARN=$(aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name rescue-request-events-v1 --query TopicArn --output text)
PRIOR_CREATED_TOPIC_ARN=$(aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name rescue-prioritization-created-v1 --query TopicArn --output text)
PRIOR_UPDATED_TOPIC_ARN=$(aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name rescue-prioritization-updated-v1 --query TopicArn --output text)

STREAM_QUEUE_URL=$(aws sqs create-queue --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name rescue-request-events-v1-stream --query QueueUrl --output text)
PRIOR_DLQ_URL=$(aws sqs create-queue --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name rescue-prioritization-evaluated-dlq --query QueueUrl --output text)
PRIOR_DLQ_ARN=$(aws sqs get-queue-attributes --endpoint-url "$ENDPOINT" --region "$REGION" --queue-url "$PRIOR_DLQ_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)

PRIOR_QUEUE_URL=$(aws sqs create-queue \
  --endpoint-url "$ENDPOINT" \
  --region "$REGION" \
  --queue-name rescue-prioritization-evaluated \
  --attributes RedrivePolicy="{\"deadLetterTargetArn\":\"$PRIOR_DLQ_ARN\",\"maxReceiveCount\":\"3\"}" \
  --query QueueUrl --output text)

echo "EVENTS_TOPIC_ARN=$EVENTS_TOPIC_ARN"
echo "PRIOR_CREATED_TOPIC_ARN=$PRIOR_CREATED_TOPIC_ARN"
echo "PRIOR_UPDATED_TOPIC_ARN=$PRIOR_UPDATED_TOPIC_ARN"
echo "STREAM_QUEUE_URL=$STREAM_QUEUE_URL"
echo "PRIOR_QUEUE_URL=$PRIOR_QUEUE_URL"
echo "PRIOR_DLQ_URL=$PRIOR_DLQ_URL"
```

### PowerShell

```powershell
$endpoint = "http://localhost:4566"
$region = "ap-southeast-1"

$eventsTopicArn = aws sns create-topic --endpoint-url $endpoint --region $region --name rescue-request-events-v1 --query TopicArn --output text
$priorCreatedTopicArn = aws sns create-topic --endpoint-url $endpoint --region $region --name rescue-prioritization-created-v1 --query TopicArn --output text
$priorUpdatedTopicArn = aws sns create-topic --endpoint-url $endpoint --region $region --name rescue-prioritization-updated-v1 --query TopicArn --output text

$streamQueueUrl = aws sqs create-queue --endpoint-url $endpoint --region $region --queue-name rescue-request-events-v1-stream --query QueueUrl --output text
$priorDlqUrl = aws sqs create-queue --endpoint-url $endpoint --region $region --queue-name rescue-prioritization-evaluated-dlq --query QueueUrl --output text
$priorDlqArn = aws sqs get-queue-attributes --endpoint-url $endpoint --region $region --queue-url $priorDlqUrl --attribute-names QueueArn --query Attributes.QueueArn --output text

$redrivePolicy = @{ deadLetterTargetArn = $priorDlqArn; maxReceiveCount = "3" } | ConvertTo-Json -Compress
$queueAttrs = @{ RedrivePolicy = $redrivePolicy } | ConvertTo-Json -Compress
$queueAttrsFile = Join-Path $PWD "tmp.create-queue-attrs.json"
Set-Content -Path $queueAttrsFile -Value $queueAttrs -NoNewline
$priorQueueUrl = aws sqs create-queue --endpoint-url $endpoint --region $region --queue-name rescue-prioritization-evaluated --attributes file://$queueAttrsFile --query QueueUrl --output text

Write-Host "EVENTS_TOPIC_ARN=$eventsTopicArn"
Write-Host "PRIOR_CREATED_TOPIC_ARN=$priorCreatedTopicArn"
Write-Host "PRIOR_UPDATED_TOPIC_ARN=$priorUpdatedTopicArn"
Write-Host "STREAM_QUEUE_URL=$streamQueueUrl"
Write-Host "PRIOR_QUEUE_URL=$priorQueueUrl"
Write-Host "PRIOR_DLQ_URL=$priorDlqUrl"
```

### Optional: create deploy-style names in LocalStack (stage suffix)

Use this only when you explicitly want local resources named like deploy resources (for example: `*-local` or `*-dev`).

### bash

```bash
STAGE=local
ENDPOINT=http://localhost:4566
REGION=ap-southeast-1

aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name "rescue-request-events-v1-$STAGE"
aws sqs create-queue --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name "rescue-request-events-v1-stream-$STAGE"
aws sqs create-queue --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name "rescue-prioritization-evaluated-dlq-$STAGE"
aws sqs create-queue --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name "rescue-prioritization-evaluated-$STAGE"
```

### PowerShell

```powershell
$stage = "local"
$endpoint = "http://localhost:4566"
$region = "ap-southeast-1"

aws sns create-topic --endpoint-url $endpoint --region $region --name "rescue-request-events-v1-$stage"
aws sqs create-queue --endpoint-url $endpoint --region $region --queue-name "rescue-request-events-v1-stream-$stage"
aws sqs create-queue --endpoint-url $endpoint --region $region --queue-name "rescue-prioritization-evaluated-dlq-$stage"
aws sqs create-queue --endpoint-url $endpoint --region $region --queue-name "rescue-prioritization-evaluated-$stage"
```

If you use deploy-style names in local, also update `.env` and `.env.json` to match those ARNs/names.

## Inspect SNS/SQS Resources

### List SNS topics

### bash

```bash
aws sns list-topics --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### PowerShell

```powershell
aws sns list-topics --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### List SQS queues

### bash

```bash
aws sqs list-queues --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### PowerShell

```powershell
aws sqs list-queues --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### List SNS subscriptions

### bash

```bash
aws sns list-subscriptions --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### PowerShell

```powershell
aws sns list-subscriptions --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### List subscriptions for a specific topic

### bash

```bash
TOPIC_ARN="arn:aws:sns:ap-southeast-1:000000000000:rescue-request-events-v1"
aws sns list-subscriptions-by-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn "$TOPIC_ARN"
```

### PowerShell

```powershell
$topicArn = "arn:aws:sns:ap-southeast-1:000000000000:rescue-request-events-v1"
aws sns list-subscriptions-by-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn $topicArn
```

### Inspect queue attributes

### bash

```bash
QUEUE_URL=$(aws sqs get-queue-url --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-prioritization-evaluated --query QueueUrl --output text)
aws sqs get-queue-attributes --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url "$QUEUE_URL" --attribute-names All
```

### PowerShell

```powershell
$queueUrl = aws sqs get-queue-url --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-prioritization-evaluated --query QueueUrl --output text
aws sqs get-queue-attributes --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url $queueUrl --attribute-names All
```
## Subscribe Queue to Topic and Wait for Messages

Important: SNS messages are consumed through subscribed SQS queues. You cannot receive directly from an SNS topic.

### A) Subscribe `rescue-request-events-v1-stream` queue to `rescue-request-events-v1` topic

### bash

```bash
ENDPOINT=http://localhost:4566
REGION=ap-southeast-1

TOPIC_ARN=$(aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name rescue-request-events-v1 --query TopicArn --output text)
QUEUE_URL=$(aws sqs get-queue-url --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name rescue-request-events-v1-stream --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes --endpoint-url "$ENDPOINT" --region "$REGION" --queue-url "$QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)

POLICY=$(cat <<EOF
{"Version":"2012-10-17","Statement":[{"Sid":"AllowRescueRequestEventsTopic","Effect":"Allow","Principal":"*","Action":"sqs:SendMessage","Resource":"$QUEUE_ARN","Condition":{"ArnEquals":{"aws:SourceArn":"$TOPIC_ARN"}}}]}
EOF
)

aws sqs set-queue-attributes --endpoint-url "$ENDPOINT" --region "$REGION" --queue-url "$QUEUE_URL" --attributes Policy="$POLICY"
aws sns subscribe --endpoint-url "$ENDPOINT" --region "$REGION" --topic-arn "$TOPIC_ARN" --protocol sqs --notification-endpoint "$QUEUE_ARN"
```

### PowerShell

```powershell
$endpoint = "http://localhost:4566"
$region = "ap-southeast-1"

$topicArn = aws sns create-topic --endpoint-url $endpoint --region $region --name rescue-request-events-v1 --query TopicArn --output text
$queueUrl = aws sqs get-queue-url --endpoint-url $endpoint --region $region --queue-name rescue-request-events-v1-stream --query QueueUrl --output text
$queueArn = aws sqs get-queue-attributes --endpoint-url $endpoint --region $region --queue-url $queueUrl --attribute-names QueueArn --query Attributes.QueueArn --output text

$policy = @{
  Version = "2012-10-17"
  Statement = @(
    @{
      Sid = "AllowRescueRequestEventsTopic"
      Effect = "Allow"
      Principal = "*"
      Action = "sqs:SendMessage"
      Resource = $queueArn
      Condition = @{ ArnEquals = @{ "aws:SourceArn" = $topicArn } }
    }
  )
} | ConvertTo-Json -Depth 8 -Compress

$attributes = @{ Policy = $policy } | ConvertTo-Json -Compress
$attrFile = Join-Path $PWD "tmp.sqs-attributes.json"
Set-Content -Path $attrFile -Value $attributes -NoNewline

aws sqs set-queue-attributes --endpoint-url $endpoint --region $region --queue-url $queueUrl --attributes file://$attrFile
aws sns subscribe --endpoint-url $endpoint --region $region --topic-arn $topicArn --protocol sqs --notification-endpoint $queueArn
```

### B) Subscribe prioritization queue to external prioritization topics

### bash

```bash
ENDPOINT=http://localhost:4566
REGION=ap-southeast-1

CREATED_TOPIC_ARN=$(aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name rescue-prioritization-created-v1 --query TopicArn --output text)
UPDATED_TOPIC_ARN=$(aws sns create-topic --endpoint-url "$ENDPOINT" --region "$REGION" --name rescue-prioritization-updated-v1 --query TopicArn --output text)
QUEUE_URL=$(aws sqs get-queue-url --endpoint-url "$ENDPOINT" --region "$REGION" --queue-name rescue-prioritization-evaluated --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes --endpoint-url "$ENDPOINT" --region "$REGION" --queue-url "$QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)

POLICY=$(cat <<EOF
{"Version":"2012-10-17","Statement":[{"Sid":"AllowPriorCreatedTopic","Effect":"Allow","Principal":"*","Action":"sqs:SendMessage","Resource":"$QUEUE_ARN","Condition":{"ArnEquals":{"aws:SourceArn":"$CREATED_TOPIC_ARN"}}},{"Sid":"AllowPriorUpdatedTopic","Effect":"Allow","Principal":"*","Action":"sqs:SendMessage","Resource":"$QUEUE_ARN","Condition":{"ArnEquals":{"aws:SourceArn":"$UPDATED_TOPIC_ARN"}}}]}
EOF
)

aws sqs set-queue-attributes --endpoint-url "$ENDPOINT" --region "$REGION" --queue-url "$QUEUE_URL" --attributes Policy="$POLICY"
aws sns subscribe --endpoint-url "$ENDPOINT" --region "$REGION" --topic-arn "$CREATED_TOPIC_ARN" --protocol sqs --notification-endpoint "$QUEUE_ARN"
aws sns subscribe --endpoint-url "$ENDPOINT" --region "$REGION" --topic-arn "$UPDATED_TOPIC_ARN" --protocol sqs --notification-endpoint "$QUEUE_ARN"
```

### PowerShell

```powershell
$endpoint = "http://localhost:4566"
$region = "ap-southeast-1"

$createdTopicArn = aws sns create-topic --endpoint-url $endpoint --region $region --name rescue-prioritization-created-v1 --query TopicArn --output text
$updatedTopicArn = aws sns create-topic --endpoint-url $endpoint --region $region --name rescue-prioritization-updated-v1 --query TopicArn --output text
$queueUrl = aws sqs get-queue-url --endpoint-url $endpoint --region $region --queue-name rescue-prioritization-evaluated --query QueueUrl --output text
$queueArn = aws sqs get-queue-attributes --endpoint-url $endpoint --region $region --queue-url $queueUrl --attribute-names QueueArn --query Attributes.QueueArn --output text

$policy = @{
  Version = "2012-10-17"
  Statement = @(
    @{
      Sid = "AllowPriorCreatedTopic"
      Effect = "Allow"
      Principal = "*"
      Action = "sqs:SendMessage"
      Resource = $queueArn
      Condition = @{ ArnEquals = @{ "aws:SourceArn" = $createdTopicArn } }
    },
    @{
      Sid = "AllowPriorUpdatedTopic"
      Effect = "Allow"
      Principal = "*"
      Action = "sqs:SendMessage"
      Resource = $queueArn
      Condition = @{ ArnEquals = @{ "aws:SourceArn" = $updatedTopicArn } }
    }
  )
} | ConvertTo-Json -Depth 8 -Compress

$attributes = @{ Policy = $policy } | ConvertTo-Json -Compress
$attrFile = Join-Path $PWD "tmp.sqs-attributes.json"
Set-Content -Path $attrFile -Value $attributes -NoNewline

aws sqs set-queue-attributes --endpoint-url $endpoint --region $region --queue-url $queueUrl --attributes file://$attrFile
aws sns subscribe --endpoint-url $endpoint --region $region --topic-arn $createdTopicArn --protocol sqs --notification-endpoint $queueArn
aws sns subscribe --endpoint-url $endpoint --region $region --topic-arn $updatedTopicArn --protocol sqs --notification-endpoint $queueArn
```

### Wait and receive messages from subscribed queue

### bash

```bash
QUEUE_URL=$(aws sqs get-queue-url --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-v1-stream --query QueueUrl --output text)
aws sqs receive-message --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url "$QUEUE_URL" --max-number-of-messages 10 --wait-time-seconds 20 --attribute-names All --message-attribute-names All
```

Continuous long-poll:

```bash
QUEUE_URL=$(aws sqs get-queue-url --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-v1-stream --query QueueUrl --output text)
while true; do
  aws sqs receive-message --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url "$QUEUE_URL" --max-number-of-messages 10 --wait-time-seconds 20 --attribute-names All --message-attribute-names All
  sleep 1
done
```

### PowerShell

```powershell
$queueUrl = aws sqs get-queue-url --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-v1-stream --query QueueUrl --output text
aws sqs receive-message --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url $queueUrl --max-number-of-messages 10 --wait-time-seconds 20 --attribute-names All --message-attribute-names All
```

Continuous long-poll:

```powershell
$queueUrl = aws sqs get-queue-url --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-name rescue-request-events-v1-stream --query QueueUrl --output text
while ($true) {
  aws sqs receive-message --endpoint-url http://localhost:4566 --region ap-southeast-1 --queue-url $queueUrl --max-number-of-messages 10 --wait-time-seconds 20 --attribute-names All --message-attribute-names All
  Start-Sleep -Seconds 1
}
```

### Publish test message to topic

### bash

```bash
TOPIC_ARN=$(aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1 --query TopicArn --output text)
aws sns publish --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn "$TOPIC_ARN" --message '{"hello":"local-topic-test"}'
```

### PowerShell

```powershell
$topicArn = aws sns create-topic --endpoint-url http://localhost:4566 --region ap-southeast-1 --name rescue-request-events-v1 --query TopicArn --output text
aws sns publish --endpoint-url http://localhost:4566 --region ap-southeast-1 --topic-arn $topicArn --message '{"hello":"local-topic-test"}'
```

## Invoke Lambda Locally

`template.local.yaml` now includes SQS event mapping for `IngestPrioritizationEvaluationsFunction`
to mirror deploy wiring. You can still invoke it directly with `sam local invoke` for deterministic tests.

### Invoke `IngestPrioritizationEvaluationsFunction` (exact command)

### bash

```bash
sam local invoke IngestPrioritizationEvaluationsFunction \
  --event sqs-event.json \
  --template-file template.local.yaml \
  --env-vars .env.json \
  --docker-network rescue-net
```

### PowerShell

```powershell
sam local invoke IngestPrioritizationEvaluationsFunction `
  --event sqs-event.json `
  --template-file template.local.yaml `
  --env-vars .env.json `
  --docker-network rescue-net
```

### Invoke `SyncIncidentCatalogFunction`

### bash

```bash
printf '{}' > sync-event.json
sam local invoke SyncIncidentCatalogFunction \
  --event sync-event.json \
  --template-file template.local.yaml \
  --env-vars .env.json \
  --docker-network rescue-net
```

### PowerShell

```powershell
'{}' | Set-Content -NoNewline sync-event.json
sam local invoke SyncIncidentCatalogFunction `
  --event sync-event.json `
  --template-file template.local.yaml `
  --env-vars .env.json `
  --docker-network rescue-net
```
## Incident Catalog Sync Test Setup

This flow verifies end-to-end IncidentTracking integration in local runtime.

### Step 1: Create or update local secret for incident sync

Secret name expected by code:
- `rescue-request-service/incident-tracking/local`

Important for local invoke:
- If IncidentTracking Service runs on your host machine, use `http://host.docker.internal:3000/api/v1/incidents` (not `http://localhost:3000/...`) because Lambda runs inside a Docker container.

### bash

```bash
aws secretsmanager create-secret \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --name rescue-request-service/incident-tracking/local \
  --secret-string '{"apiUrl":"https://incident-service.krittamark.com/api/v1/incidents","apiKey":"<YOUR_API_KEY>","accept":"application/json","transactionIdHeader":"X-IncidentTNX-Id"}'
```

If the secret already exists:

```bash
aws secretsmanager put-secret-value \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --secret-id rescue-request-service/incident-tracking/local \
  --secret-string '{"apiUrl":"https://incident-service.krittamark.com/api/v1/incidents","apiKey":"<YOUR_API_KEY>","accept":"application/json","transactionIdHeader":"X-IncidentTNX-Id"}'
```

### PowerShell

```powershell
$secretPayload = @{
  apiUrl = "http://host.docker.internal:3000/api/v1/incidents"
  apiKey = "<YOUR_API_KEY>"
  accept = "application/json"
  transactionIdHeader = "X-IncidentTNX-Id"
} | ConvertTo-Json -Compress

$secretFile = Join-Path $PWD "tmp.incident-secret.json"
Set-Content -Path $secretFile -Value $secretPayload -NoNewline

aws secretsmanager create-secret `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --name rescue-request-service/incident-tracking/local `
  --secret-string file://$secretFile
```

If the secret already exists:

```powershell
$secretPayload = @{
  apiUrl = "http://host.docker.internal:3000/api/v1/incidents"
  apiKey = "<YOUR_API_KEY>"
  accept = "application/json"
  transactionIdHeader = "X-IncidentTNX-Id"
} | ConvertTo-Json -Compress

$secretFile = Join-Path $PWD "tmp.incident-secret.json"
Set-Content -Path $secretFile -Value $secretPayload -NoNewline

aws secretsmanager put-secret-value `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --secret-id rescue-request-service/incident-tracking/local `
  --secret-string file://$secretFile
```

### Step 2: Trigger sync Lambda to call IncidentTracking Service

### bash

```bash
printf '{}' > sync-event.json
sam local invoke SyncIncidentCatalogFunction \
  --event sync-event.json \
  --template-file template.local.yaml \
  --env-vars .env.json \
  --docker-network rescue-net
```

### PowerShell

```powershell
'{}' | Set-Content -NoNewline sync-event.json
sam local invoke SyncIncidentCatalogFunction `
  --event sync-event.json `
  --template-file template.local.yaml `
  --env-vars .env.json `
  --docker-network rescue-net
```

### Step 3: Verify synced catalog data

### bash

```bash
curl "http://127.0.0.1:3000/v1/incidents?limit=20"
aws dynamodb scan --endpoint-url http://localhost:4566 --region ap-southeast-1 --table-name IncidentCatalogTable
```

### PowerShell

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:3000/v1/incidents?limit=20" -Method Get
aws dynamodb scan --endpoint-url http://localhost:4566 --region ap-southeast-1 --table-name IncidentCatalogTable
```

### Optional: call IncidentTracking Service directly from terminal

### bash

```bash
curl -X GET "https://incident-service.krittamark.com/api/v1/incidents" \
  -H "api-key: <YOUR_API_KEY>" \
  -H "Accept: application/json" \
  -H "X-IncidentTNX-Id: local-test-$(date +%s)"
```

### PowerShell

```powershell
Invoke-RestMethod -Method Get -Uri "https://incident-service.krittamark.com/api/v1/incidents" -Headers @{
  "api-key" = "<YOUR_API_KEY>"
  "Accept" = "application/json"
  "X-IncidentTNX-Id" = "local-test-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
}
```

## Prioritization Result Ingest Test Setup

This flow verifies `IngestPrioritizationEvaluationsFunction` end-to-end with valid correlation.

### Step 1: Create a rescue request

Use a valid UUID `incidentId` and a new phone number.

### bash

```bash
curl -X POST http://127.0.0.1:3000/v1/rescue-requests \
  -H "Content-Type: application/json" \
  -d '{
    "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
    "requestType": "MEDICAL",
    "description": "Need evacuation support",
    "peopleCount": 3,
    "latitude": 13.7563,
    "longitude": 100.5018,
    "contactName": "Local Tester",
    "contactPhone": "0890000001",
    "sourceChannel": "WEB"
  }'
```

### PowerShell

```powershell
$body = @{
  incidentId = "019c774d-1ac5-758b-ae95-5cd4aeb89258"
  requestType = "MEDICAL"
  description = "Need evacuation support"
  peopleCount = 3
  latitude = 13.7563
  longitude = 100.5018
  contactName = "Local Tester"
  contactPhone = "0890000001"
  sourceChannel = "WEB"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3000/v1/rescue-requests" -ContentType "application/json" -Body $body
```

Save `requestId` from the response.

### Step 2: Read correlation source event id from DynamoDB

`header.correlationId` in incoming evaluation must match `CURRENT.latestPrioritySourceEventId`.

### bash

```bash
REQUEST_ID=<REQUEST_ID_FROM_CREATE_RESPONSE>
aws dynamodb get-item \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --table-name RescueRequestTable \
  --key "{\"PK\":{\"S\":\"REQ#$REQUEST_ID\"},\"SK\":{\"S\":\"CURRENT\"}}" \
  --query 'Item.latestPrioritySourceEventId.S' \
  --output text
```

### PowerShell

```powershell
$requestId = "<REQUEST_ID_FROM_CREATE_RESPONSE>"
$key = "{\"PK\":{\"S\":\"REQ#$requestId\"},\"SK\":{\"S\":\"CURRENT\"}}"
aws dynamodb get-item `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --table-name RescueRequestTable `
  --key $key `
  --query "Item.latestPrioritySourceEventId.S" `
  --output text
```

Save the value as `CORRELATION_ID`.

### Step 3: Update `sqs-event.json` with request and correlation IDs

`submittedAt` is optional for ingest validation. Keep it in the payload when available for richer traceability.

### bash

```bash
export REQUEST_ID=<REQUEST_ID_FROM_CREATE_RESPONSE>
export CORRELATION_ID=<LATEST_PRIORITY_SOURCE_EVENT_ID>

python - <<'PY'
import json
import os
import uuid
from datetime import datetime, timezone

request_id = os.environ["REQUEST_ID"]
correlation_id = os.environ["CORRELATION_ID"]
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

with open("sqs-event.json", "r", encoding="utf-8") as f:
    event = json.load(f)

message = json.loads(event["Records"][0]["body"])
message["header"]["messageType"] = "RescueRequestEvaluatedEvent"
message["header"]["messageId"] = str(uuid.uuid4())
message["header"]["correlationId"] = correlation_id
message["header"]["sentAt"] = now
message["header"]["version"] = "1"

message["body"]["requestId"] = request_id
message["body"]["incidentId"] = str(uuid.uuid4())
message["body"]["evaluateId"] = str(uuid.uuid4())
message["body"]["submittedAt"] = now
message["body"]["lastEvaluatedAt"] = now

event["Records"][0]["body"] = json.dumps(message, separators=(",", ":"))

with open("sqs-event.json", "w", encoding="utf-8") as f:
    json.dump(event, f, indent=2)

print("sqs-event.json updated")
PY
```

### PowerShell

```powershell
$requestId = "<REQUEST_ID_FROM_CREATE_RESPONSE>"
$correlationId = "<LATEST_PRIORITY_SOURCE_EVENT_ID>"
$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$event = Get-Content sqs-event.json -Raw | ConvertFrom-Json
$message = $event.Records[0].body | ConvertFrom-Json

$message.header.messageType = "RescueRequestEvaluatedEvent"
$message.header.messageId = [guid]::NewGuid().ToString()
$message.header.correlationId = $correlationId
$message.header.sentAt = $now
$message.header.version = "1"

$message.body.requestId = $requestId
$message.body.incidentId = [guid]::NewGuid().ToString()
$message.body.evaluateId = [guid]::NewGuid().ToString()
$message.body.submittedAt = $now
$message.body.lastEvaluatedAt = $now

$event.Records[0].body = ($message | ConvertTo-Json -Depth 10 -Compress)
$event | ConvertTo-Json -Depth 10 | Set-Content sqs-event.json
Write-Host "sqs-event.json updated"
```
### Step 4: Invoke ingest function

### bash

```bash
sam local invoke IngestPrioritizationEvaluationsFunction \
  --event sqs-event.json \
  --template-file template.local.yaml \
  --env-vars .env.json \
  --docker-network rescue-net
```

### PowerShell

```powershell
sam local invoke IngestPrioritizationEvaluationsFunction `
  --event sqs-event.json `
  --template-file template.local.yaml `
  --env-vars .env.json `
  --docker-network rescue-net
```

### Step 5: Verify request current state was updated

### bash

```bash
REQUEST_ID=<REQUEST_ID_FROM_CREATE_RESPONSE>
curl "http://127.0.0.1:3000/v1/rescue-requests/$REQUEST_ID/current"

aws dynamodb get-item \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --table-name RescueRequestTable \
  --key "{\"PK\":{\"S\":\"REQ#$REQUEST_ID\"},\"SK\":{\"S\":\"CURRENT\"}}" \
  --query 'Item.{status:status.S,priorityScore:priorityScore.N,priorityLevel:priorityLevel.S,latestPriorityEvaluationId:latestPriorityEvaluationId.S,lastPriorityIngestedAt:lastPriorityIngestedAt.S}'
```

### PowerShell

```powershell
$requestId = "<REQUEST_ID_FROM_CREATE_RESPONSE>"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:3000/v1/rescue-requests/$requestId/current"

$key = "{\"PK\":{\"S\":\"REQ#$requestId\"},\"SK\":{\"S\":\"CURRENT\"}}"
aws dynamodb get-item `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --table-name RescueRequestTable `
  --key $key `
  --query "Item.{status:status.S,priorityScore:priorityScore.N,priorityLevel:priorityLevel.S,latestPriorityEvaluationId:latestPriorityEvaluationId.S,lastPriorityIngestedAt:lastPriorityIngestedAt.S}"
```

## Secrets Manager Commands (LocalStack)

### List secrets

### bash

```bash
aws secretsmanager list-secrets --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### PowerShell

```powershell
aws secretsmanager list-secrets --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### Get secret value

### bash

```bash
aws secretsmanager get-secret-value --endpoint-url http://localhost:4566 --region ap-southeast-1 --secret-id rescue-request-service/incident-tracking/local
```

### PowerShell

```powershell
aws secretsmanager get-secret-value --endpoint-url http://localhost:4566 --region ap-southeast-1 --secret-id rescue-request-service/incident-tracking/local
```

### Update secret value

### bash

```bash
aws secretsmanager put-secret-value \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --secret-id rescue-request-service/incident-tracking/local \
  --secret-string '{"apiUrl":"https://incident-service.krittamark.com/api/v1/incidents","apiKey":"<YOUR_API_KEY>","accept":"application/json","transactionIdHeader":"X-IncidentTNX-Id"}'
```

### PowerShell

```powershell
$secretPayload = @{
  apiUrl = "https://incident-service.krittamark.com/api/v1/incidents"
  apiKey = "<YOUR_API_KEY>"
  accept = "application/json"
  transactionIdHeader = "X-IncidentTNX-Id"
} | ConvertTo-Json -Compress

aws secretsmanager put-secret-value `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --secret-id rescue-request-service/incident-tracking/local `
  --secret-string $secretPayload
```

### Delete secret in LocalStack

### bash

```bash
aws secretsmanager delete-secret \
  --endpoint-url http://localhost:4566 \
  --region ap-southeast-1 \
  --secret-id rescue-request-service/incident-tracking/local \
  --force-delete-without-recovery
```

### PowerShell

```powershell
aws secretsmanager delete-secret `
  --endpoint-url http://localhost:4566 `
  --region ap-southeast-1 `
  --secret-id rescue-request-service/incident-tracking/local `
  --force-delete-without-recovery
```

## Local Validation and Deploy-Parity Checklist

Run these commands to keep local checks close to deploy behavior.

### Validate SAM templates

### bash

```bash
sam validate --template-file template.yaml
sam validate --template-file template.local.yaml
```

### PowerShell

```powershell
sam validate --template-file template.yaml
sam validate --template-file template.local.yaml
```

### Build templates

### bash

```bash
sam build --template-file template.yaml --use-container
sam build --template-file template.local.yaml --use-container
```

### PowerShell

```powershell
sam build --template-file template.yaml --use-container
sam build --template-file template.local.yaml --use-container
```

### Local DB and runtime management

### bash

```bash
make local-db-start
make local-db-reset
make local-db-stop
make local-start
make local-stop
```

### PowerShell

```powershell
make local-db-start
make local-db-reset
make local-db-stop
make local-start
make local-stop
```

### Verify LocalStack health and resources

### bash

```bash
curl http://localhost:4566/_localstack/health
aws dynamodb list-tables --endpoint-url http://localhost:4566 --region ap-southeast-1
aws sns list-topics --endpoint-url http://localhost:4566 --region ap-southeast-1
aws sqs list-queues --endpoint-url http://localhost:4566 --region ap-southeast-1
aws secretsmanager list-secrets --endpoint-url http://localhost:4566 --region ap-southeast-1
aws events list-rules --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### PowerShell

```powershell
Invoke-RestMethod -Uri http://localhost:4566/_localstack/health -Method Get
aws dynamodb list-tables --endpoint-url http://localhost:4566 --region ap-southeast-1
aws sns list-topics --endpoint-url http://localhost:4566 --region ap-southeast-1
aws sqs list-queues --endpoint-url http://localhost:4566 --region ap-southeast-1
aws secretsmanager list-secrets --endpoint-url http://localhost:4566 --region ap-southeast-1
aws events list-rules --endpoint-url http://localhost:4566 --region ap-southeast-1
```

### Runtime logs

### bash

```bash
docker logs -f localstack
```

### PowerShell

```powershell
docker logs -f localstack
```

## Deploy to AWS (SAM Package + CloudFormation)

### Step 0: Prepare deployment bucket

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
export AWS_DEFAULT_REGION="ap-southeast-2"
```

### PowerShell

```powershell
$env:AWS_ACCESS_KEY_ID="xxxx"
$env:AWS_SECRET_ACCESS_KEY="xxxx"
$env:AWS_DEFAULT_REGION="ap-southeast-2"
```

### Step 2: Verify active identity

### bash

```bash
aws sts get-caller-identity
```

### PowerShell

```powershell
aws sts get-caller-identity
```

### Step 2.1: Optional APPDATA fix for SAM on Windows

### bash (Git Bash on Windows)

```bash
export APPDATA="$USERPROFILE/AppData/Roaming"
```

### PowerShell

```powershell
$env:APPDATA = "$env:USERPROFILE\\AppData\\Roaming"
```

### Step 3: Build

### bash

```bash
sam build --template-file template.yaml --use-container
```

### PowerShell

```powershell
sam build --template-file template.yaml --use-container
```

### Step 4: Package

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

### Step 5: Deploy with CloudFormation

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

### Step 6: Verify stack outputs

### bash

```bash
aws cloudformation describe-stacks --stack-name rescue-request-service-dev --region ap-southeast-2
```

### PowerShell

```powershell
aws cloudformation describe-stacks --stack-name rescue-request-service-dev --region ap-southeast-2
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

## Tests

### Unit tests

### bash

```bash
make test-unit
```

### PowerShell

```powershell
make test-unit
```

### Integration tests

### bash

```bash
make test-integration
```

### PowerShell

```powershell
make test-integration
```

## API Endpoints

### Public
- `POST /v1/rescue-requests`
- `POST /v1/citizen/tracking/lookup`
- `GET /v1/citizen/rescue-requests/{requestId}/status`
- `POST /v1/citizen/rescue-requests/{requestId}/updates`
- `GET /v1/citizen/rescue-requests/{requestId}/updates`
- `GET /v1/incidents`

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

### Internal
- `GET /v1/internal/incidents/catalog`

## Troubleshooting

### Local runtime

- If Lambda cannot connect to DynamoDB in local invoke, confirm `.env.json` has `DYNAMODB_ENDPOINT=http://localstack:4566`.
- If tables are missing, run `make local-db-start` and check with `aws dynamodb list-tables --endpoint-url http://localhost:4566 --region ap-southeast-1`.
- If `SNS_TOPIC_ARN not set`, create the topic and ensure `.env` and `.env.json` match the same ARN.
- If ingest validation fails, verify message fields and especially `header.correlationId` equals `latestPrioritySourceEventId` in the current DynamoDB item.
- If incident sync fails with secret errors, verify the secret exists and contains valid JSON with required keys `apiUrl` and `apiKey`.
- If sync fails with `Incident tracking secret must be valid JSON`, inspect current value using `aws secretsmanager get-secret-value --endpoint-url http://localhost:4566 --region ap-southeast-1 --secret-id rescue-request-service/incident-tracking/local --query SecretString --output text` and rewrite with valid JSON.
- If sync fails with `IncidentTracking Service is unreachable` and your incident service runs on host machine, set secret `apiUrl` to `http://host.docker.internal:3000/api/v1/incidents` instead of `http://localhost:3000/...`.
- If AWS CLI returns `Unable to locate credentials` in local mode, set `AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`, `AWS_DEFAULT_REGION=ap-southeast-1` before running commands.
- If you get `Service 'secretsmanager' is not enabled`, recreate LocalStack after pulling latest compose config:
  - `make local-db-stop`
  - `make local-db-start`
  - verify with `aws secretsmanager list-secrets --endpoint-url http://localhost:4566 --region ap-southeast-1`
- If Docker/LocalStack is unavailable, check `docker ps` and restart Docker Desktop.

### Deployment

- If `sam build --use-container` fails, ensure Docker daemon is running.
- If `sam package` fails, verify S3 bucket region and IAM permissions.
- If CloudFormation deploy fails with capability errors, include `--capabilities CAPABILITY_IAM`.
- If stack rolls back, inspect events:

### bash

```bash
aws cloudformation describe-stack-events --stack-name rescue-request-service-dev --region ap-southeast-2
```

### PowerShell

```powershell
aws cloudformation describe-stack-events --stack-name rescue-request-service-dev --region ap-southeast-2
```
