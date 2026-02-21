#!/usr/bin/env bash
set -euo pipefail

REGION="us-east-1"
ENDPOINT="http://localhost:4566"
TABLE_NAME="rescue-requests"
CREATED_TOPIC="rescue-request-created"
STATUS_TOPIC="rescue-request-status-changed"
DLQ_NAME="rescue-request-dlq"

echo "==> Creating DynamoDB table: ${TABLE_NAME}"
awslocal dynamodb create-table \
  --region "${REGION}" \
  --table-name "${TABLE_NAME}" \
  --attribute-definitions \
    AttributeName=requestId,AttributeType=S \
    AttributeName=incidentId,AttributeType=S \
  --key-schema \
    AttributeName=requestId,KeyType=HASH \
  --global-secondary-indexes '[
    {
      "IndexName": "incidentId-index",
      "KeySchema": [{"AttributeName":"incidentId","KeyType":"HASH"}],
      "Projection": {"ProjectionType":"ALL"},
      "ProvisionedThroughput": {"ReadCapacityUnits":5,"WriteCapacityUnits":5}
    }
  ]' \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url "${ENDPOINT}" \
  || echo "Table may already exist, continuing..."

echo "==> Creating SNS topic: ${CREATED_TOPIC}"
awslocal sns create-topic \
  --region "${REGION}" \
  --name "${CREATED_TOPIC}" \
  --endpoint-url "${ENDPOINT}"

echo "==> Creating SNS topic: ${STATUS_TOPIC}"
awslocal sns create-topic \
  --region "${REGION}" \
  --name "${STATUS_TOPIC}" \
  --endpoint-url "${ENDPOINT}"

echo "==> Creating SQS dead-letter queue: ${DLQ_NAME}"
awslocal sqs create-queue \
  --region "${REGION}" \
  --queue-name "${DLQ_NAME}" \
  --endpoint-url "${ENDPOINT}"

echo "==> LocalStack bootstrap complete."
