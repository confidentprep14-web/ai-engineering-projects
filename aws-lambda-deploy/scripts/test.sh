#!/bin/bash
set -e
source .env
source .deployed.env 2>/dev/null || { echo "Run deploy.sh first"; exit 1; }

echo "=== Testing deployed Chat API ==="

echo "[1/2] GET /health"
curl -sf "${API_URL}/health" | jq .

echo ""
echo "[2/2] POST /chat (streaming)"
curl -sN -X POST "${API_URL}/chat" \
    -H "Content-Type: application/json" \
    -d '{"message": "Say hello in exactly three words."}'

echo ""
echo "=== Test complete ==="
