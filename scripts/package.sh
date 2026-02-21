#!/usr/bin/env bash
set -euo pipefail

DIST_DIR="dist"
ZIP_FILE="${DIST_DIR}/lambda.zip"

if [ ! -d "${DIST_DIR}" ]; then
  echo "ERROR: dist/ directory not found. Run scripts/build.sh first."
  exit 1
fi

echo "==> Packaging Lambda deployment artifact..."
cd "${DIST_DIR}"
zip -r lambda.zip . -x "lambda.zip"
cd ..

echo "==> Package created: ${ZIP_FILE}"
