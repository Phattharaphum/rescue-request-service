#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Deploying to prod..."
sam build --template-file template.yaml
sam deploy --template-file .aws-sam/build/template.yaml --config-env prod
echo "Deploy complete."
