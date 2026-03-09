#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Building SAM application..."
sam build --template-file template.yaml
echo "Build complete."
