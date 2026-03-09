#!/bin/bash
set -e

ENDPOINT="${DYNAMODB_ENDPOINT:-http://localhost:8000}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo "Creating RescueRequestTable..."
aws dynamodb create-table \
  --table-name RescueRequestTable \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url "$ENDPOINT" \
  --region "$REGION" \
  2>/dev/null || echo "RescueRequestTable already exists"

echo "Creating IdempotencyTable..."
aws dynamodb create-table \
  --table-name IdempotencyTable \
  --attribute-definitions \
    AttributeName=idempotencyKeyHash,AttributeType=S \
  --key-schema \
    AttributeName=idempotencyKeyHash,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url "$ENDPOINT" \
  --region "$REGION" \
  2>/dev/null || echo "IdempotencyTable already exists"

echo "Tables created successfully."
