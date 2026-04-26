#!/bin/bash
set -e
BASE_URL="${1:-http://localhost:3000}"

echo "Running smoke tests against $BASE_URL..."

echo "1. Create rescue request..."
RESPONSE=$(curl -s -X POST "$BASE_URL/v1/rescue-requests" \
  -H "Content-Type: application/json" \
  -d '{
    "incidentId": "incident-smoke-001",
    "requestType": "EVACUATION",
    "description": "Smoke test request",
    "peopleCount": 3,
    "latitude": 13.7563,
    "longitude": 100.5018,
    "contactName": "Smoke Test",
    "contactPhone": "0899999999",
    "sourceChannel": "WEB"
  }')
echo "Response: $RESPONSE"

REQUEST_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('requestId',''))" 2>/dev/null || echo "")

if [ -n "$REQUEST_ID" ]; then
  echo "2. Get rescue request..."
  curl -s "$BASE_URL/v1/rescue-requests/$REQUEST_ID" | python3 -m json.tool

  echo "3. Get current state..."
  curl -s "$BASE_URL/v1/rescue-requests/$REQUEST_ID/current" | python3 -m json.tool

  echo "4. List events..."
  curl -s "$BASE_URL/v1/rescue-requests/$REQUEST_ID/events" | python3 -m json.tool
fi

echo "Smoke tests complete!"
