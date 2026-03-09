#!/bin/bash
set -e

ENDPOINT="${DYNAMODB_ENDPOINT:-http://localhost:4566}"
REGION="${AWS_REGION:-ap-southeast-1}"

wait_for_dynamodb() {
  local retries=30
  local delay=2
  local i

  echo "Waiting for DynamoDB endpoint at $ENDPOINT ..."
  for i in $(seq 1 "$retries"); do
    if aws dynamodb list-tables --endpoint-url "$ENDPOINT" --region "$REGION" >/dev/null 2>&1; then
      echo "DynamoDB endpoint is ready."
      return 0
    fi
    sleep "$delay"
  done

  echo "DynamoDB endpoint is not ready after $((retries * delay)) seconds."
  return 1
}

table_exists() {
  local table_name="$1"
  aws dynamodb describe-table \
    --table-name "$table_name" \
    --endpoint-url "$ENDPOINT" \
    --region "$REGION" >/dev/null 2>&1
}

create_rescue_request_table() {
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
    --region "$REGION" >/dev/null
}

create_idempotency_table() {
  echo "Creating IdempotencyTable..."
  aws dynamodb create-table \
    --table-name IdempotencyTable \
    --attribute-definitions \
      AttributeName=idempotencyKeyHash,AttributeType=S \
    --key-schema \
      AttributeName=idempotencyKeyHash,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url "$ENDPOINT" \
    --region "$REGION" >/dev/null
}

ensure_table() {
  local table_name="$1"
  local create_func="$2"

  if table_exists "$table_name"; then
    echo "$table_name already exists."
    return 0
  fi

  "$create_func"
  echo "$table_name created."
}

wait_for_dynamodb
ensure_table "RescueRequestTable" "create_rescue_request_table"
ensure_table "IdempotencyTable" "create_idempotency_table"
echo "Tables are ready."
