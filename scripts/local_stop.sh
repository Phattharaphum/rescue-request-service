#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "Stopping local environment..."
cd local && docker-compose down
echo "Local environment stopped."
