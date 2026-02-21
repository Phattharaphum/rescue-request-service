#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3000}"

echo "==> Smoke tests against ${BASE_URL}"
PASS=0
FAIL=0

check() {
  local description="$1"
  local expected_status="$2"
  local actual_status="$3"

  if [ "${actual_status}" -eq "${expected_status}" ]; then
    echo "  [PASS] ${description} (HTTP ${actual_status})"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] ${description} — expected HTTP ${expected_status}, got HTTP ${actual_status}"
    FAIL=$((FAIL + 1))
  fi
}

# 1. Create rescue request
echo ""
echo "--- POST /v1/requests ---"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{"incidentId":"SMOKE-001","requesterName":"Smoke Tester","description":"Smoke test request","location":"Test Location"}')
BODY=$(echo "${RESPONSE}" | head -n1)
STATUS=$(echo "${RESPONSE}" | tail -n1)
check "Create rescue request" 201 "${STATUS}"
REQUEST_ID=$(echo "${BODY}" | grep -o '"requestId":"[^"]*"' | cut -d'"' -f4 || true)
echo "     requestId: ${REQUEST_ID}"

# 2. Idempotent create (should return 200)
echo ""
echo "--- POST /v1/requests (idempotent) ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{"incidentId":"SMOKE-001","requesterName":"Smoke Tester","description":"Smoke test request","location":"Test Location"}')
check "Idempotent create returns 200" 200 "${STATUS}"

# 3. Get by ID
echo ""
echo "--- GET /v1/requests/{id} ---"
if [ -n "${REQUEST_ID}" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/requests/${REQUEST_ID}")
  check "Get rescue request by ID" 200 "${STATUS}"
else
  echo "  [SKIP] requestId not captured"
fi

# 4. Search by incidentId
echo ""
echo "--- GET /v1/requests?incidentId=SMOKE-001 ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/requests?incidentId=SMOKE-001")
check "Search requests by incidentId" 200 "${STATUS}"

# 5. Patch status
echo ""
echo "--- PATCH /v1/requests/{id}/status ---"
if [ -n "${REQUEST_ID}" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "${BASE_URL}/v1/requests/${REQUEST_ID}/status" \
    -H "Content-Type: application/json" \
    -d '{"status":"DISPATCHED","reason":"Smoke test dispatch","version":1}')
  check "Patch request status to DISPATCHED" 200 "${STATUS}"
else
  echo "  [SKIP] requestId not captured"
fi

# 6. Get 404
echo ""
echo "--- GET /v1/requests/nonexistent ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/requests/nonexistent-id-00000")
check "Get non-existent request returns 404" 404 "${STATUS}"

echo ""
echo "==> Results: ${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
