#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Deploying to prod..."
sam build --template-file template.yaml
sam deploy --config-env prod
echo "Deploy complete."
