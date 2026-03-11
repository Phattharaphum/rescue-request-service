#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Deploying to dev..."
sam build --template-file template.yaml
sam deploy --template-file .aws-sam/build/template.yaml --config-env default
echo "Deploy complete."
