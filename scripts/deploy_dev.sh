#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Deploying to dev..."
sam build --template-file template.yaml
sam deploy --config-env default
echo "Deploy complete."
