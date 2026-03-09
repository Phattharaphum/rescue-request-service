#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Starting LocalStack..."
cd local && docker-compose up -d
sleep 3
echo "Creating tables..."
cd dynamodb && bash create_tables.sh
echo "Local environment ready."
echo "Run 'sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json' to start the API."
