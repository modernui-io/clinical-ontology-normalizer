#!/bin/bash
# Start backend with ML models pre-warmed for NLP extraction
# Usage: ./scripts/start_nlp_ready.sh

set -e
cd "$(dirname "$0")/.."

echo "=== Backend Startup with NLP Pre-warming ==="

# 1. Kill any existing processes on port 8000
echo "[1/5] Cleaning up port 8000..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
sleep 1

# 2. Start backend server
echo "[2/5] Starting backend server..."
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "       Backend PID: $BACKEND_PID"

# 3. Wait for server to be ready
echo "[3/5] Waiting for server startup..."
for i in {1..30}; do
    if curl -s --max-time 2 http://localhost:8000/api/v1/nlp/samples > /dev/null 2>&1; then
        echo "       Server ready after ${i}s"
        break
    fi
    sleep 1
done

# 4. Pre-warm ML models with test extraction
echo "[4/5] Pre-warming ML models (first request loads models)..."
WARMUP_RESULT=$(curl -s --max-time 60 http://localhost:8000/api/v1/nlp/extract \
    -H 'Content-Type: application/json' \
    -d '{"text": "Patient has diabetes and hypertension.", "use_ml_models": true}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK - {d.get(\"entity_count\", 0)} entities in {d.get(\"processing_time_ms\", 0):.0f}ms')" 2>/dev/null || echo "FAILED")
echo "       Warmup: $WARMUP_RESULT"

# 5. Verify with second request (should be fast now)
echo "[5/5] Verifying extraction speed..."
VERIFY_RESULT=$(curl -s --max-time 10 http://localhost:8000/api/v1/nlp/extract \
    -H 'Content-Type: application/json' \
    -d '{"text": "Metformin 1000mg twice daily for type 2 diabetes.", "use_ml_models": true}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK - {d.get(\"entity_count\", 0)} entities in {d.get(\"processing_time_ms\", 0):.0f}ms')" 2>/dev/null || echo "FAILED")
echo "       Verify: $VERIFY_RESULT"

echo ""
echo "=== Startup Complete ==="
echo "Backend running at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo "Logs at: /tmp/backend.log"
