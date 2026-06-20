#!/bin/bash
set -e

echo "=== Docker Verification Script ==="

echo "[1/4] Building image..."
docker build -t chat-api . --quiet
echo "✓ Image built"

echo "[2/4] Starting with compose..."
docker compose up -d
sleep 15   # wait for startup

echo "[3/4] Checking health..."
STATUS=$(docker compose ps --format json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['Health'])" 2>/dev/null || echo "unknown")
if [ "$STATUS" = "healthy" ]; then
    echo "✓ Container healthy"
else
    echo "⚠ Health status: $STATUS (may still be starting)"
fi

echo "[4/4] Testing endpoints..."
HEALTH=$(curl -s http://localhost:8000/health)
echo "Health: $HEALTH"

echo ""
echo "=== Making test request ==="
curl -N -s -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Say the word hello"}' \
     -H "Accept: text/event-stream" &
CURL_PID=$!
sleep 5
kill $CURL_PID 2>/dev/null || true

echo ""
echo "=== Checking stats ==="
curl -s http://localhost:8000/stats | python3 -m json.tool

echo ""
docker compose down
echo "✓ Compose stopped"
echo "=== All checks done ==="
