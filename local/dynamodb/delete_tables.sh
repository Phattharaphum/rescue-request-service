#!/bin/bash
set -e

ENDPOINT="${DYNAMODB_ENDPOINT:-http://localhost:8000}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo "Deleting RescueRequestTable..."
aws dynamodb delete-table \
  --table-name RescueRequestTable \
  --endpoint-url "$ENDPOINT" \
  --region "$REGION" \
  2>/dev/null || echo "RescueRequestTable does not exist"

echo "Deleting IdempotencyTable..."
aws dynamodb delete-table \
  --table-name IdempotencyTable \
  --endpoint-url "$ENDPOINT" \
  --region "$REGION" \
  2>/dev/null || echo "IdempotencyTable does not exist"

echo "Tables deleted."
