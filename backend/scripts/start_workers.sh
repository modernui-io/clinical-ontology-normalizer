#!/bin/bash
# Start multiple RQ workers for bulk MIMIC NLP processing
# Usage: bash scripts/start_workers.sh [num_workers]

set -e

NUM_WORKERS=${1:-4}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Fix macOS fork() crash with Objective-C runtime
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Load environment
if [ -f "$BACKEND_DIR/.env" ]; then
    export $(cat "$BACKEND_DIR/.env" | grep -v '^#' | grep -v '^$' | xargs)
fi

REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# Suppress SQLAlchemy SQL echo to reduce I/O overhead
export DEBUG=false

# Kill any existing workers
pkill -f "rq worker" 2>/dev/null || true
sleep 2

echo "Starting $NUM_WORKERS RQ workers..."
echo "  Redis: $REDIS_URL"
echo "  Queues: document_processing, graph_building, default"
echo "  Logs: /tmp/rq_worker_*.log"

cd "$BACKEND_DIR"
for i in $(seq 1 $NUM_WORKERS); do
    nohup uv run rq worker \
        --url "$REDIS_URL" \
        document_processing graph_building default \
        > /tmp/rq_worker_${i}.log 2>&1 &
    echo "  Worker $i: PID $!"
done

echo ""
echo "Workers started. Monitor with:"
echo "  tail -f /tmp/rq_worker_1.log"
echo "  python3 -c \"import redis; r=redis.from_url('$REDIS_URL'); print(f'Queue: {r.llen(\\\"rq:queue:document_processing\\\")} jobs')\""
