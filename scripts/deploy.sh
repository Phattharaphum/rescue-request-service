#!/usr/bin/env bash
set -euo pipefail

STAGE="${1:-}"
if [ -z "${STAGE}" ]; then
  echo "Usage: $0 <stage>"
  echo "  stage: dev | prod"
  exit 1
fi

STACK_NAME="rescue-request-service-${STAGE}"
TEMPLATE_FILE="infra/cfn/template.yaml"
PARAMS_FILE="infra/params/${STAGE}.json"
ZIP_FILE="dist/lambda.zip"

if [ ! -f "${PARAMS_FILE}" ]; then
  echo "ERROR: Parameters file not found: ${PARAMS_FILE}"
  exit 1
fi

if [ ! -f "${ZIP_FILE}" ]; then
  echo "ERROR: Lambda package not found: ${ZIP_FILE}. Run scripts/package.sh first."
  exit 1
fi

echo "==> Uploading Lambda package to S3..."
S3_BUCKET="${RESCUE_REQUEST_S3_BUCKET:-rescue-request-deploy-${STAGE}}"
S3_KEY="lambda/$(date +%Y%m%d%H%M%S)/lambda.zip"

aws s3 cp "${ZIP_FILE}" "s3://${S3_BUCKET}/${S3_KEY}"

echo "==> Deploying CloudFormation stack: ${STACK_NAME}..."
aws cloudformation deploy \
  --template-file "${TEMPLATE_FILE}" \
  --stack-name "${STACK_NAME}" \
  --parameter-overrides "$(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' "${PARAMS_FILE}" | tr '\n' ' ')" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

echo "==> Deployment to ${STAGE} complete."
