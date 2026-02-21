#!/usr/bin/env bash
set -euo pipefail

echo "==> Building TypeScript..."
npm run build
echo "==> Build complete. Output in dist/"
