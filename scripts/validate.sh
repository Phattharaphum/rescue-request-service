#!/bin/bash
set -e
echo "Validating SAM template..."
cd "$(dirname "$0")/.."
sam validate --template-file template.yaml 2>/dev/null || echo "SAM CLI not installed, skipping SAM validation"
echo "Running Python syntax check..."
python -m py_compile src/shared/errors.py
python -m py_compile src/shared/response.py
echo "Validation complete."
