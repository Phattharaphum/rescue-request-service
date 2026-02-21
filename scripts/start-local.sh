#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="local/docker-compose.yml"
BOOTSTRAP_SCRIPT="local/init/bootstrap.sh"
SAM_TEMPLATE="infra/sam/template.local.yaml"

echo "==> Starting LocalStack via Docker Compose..."
docker compose -f "${COMPOSE_FILE}" up -d

echo "==> Waiting for LocalStack to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:4566/_localstack/health | grep -q '"dynamodb": "available"'; then
    echo "    LocalStack is ready."
    break
  fi
  if [ "${i}" -eq 30 ]; then
    echo "ERROR: LocalStack did not become ready in time."
    exit 1
  fi
  echo "    Waiting... (${i}/30)"
  sleep 2
done

echo "==> Running bootstrap script..."
bash "${BOOTSTRAP_SCRIPT}"

echo "==> Building TypeScript..."
npm run build

echo "==> Starting SAM local API..."
sam local start-api \
  --template "${SAM_TEMPLATE}" \
  --env-vars local/env.json \
  --docker-network host \
  --port 3000
