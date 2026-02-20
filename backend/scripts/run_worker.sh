#!/bin/bash
# RQ Worker startup script
# Reads REDIS_URL from .env file to ensure consistency with the API

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env if it exists
if [ -f "$BACKEND_DIR/.env" ]; then
    echo "Loading environment from $BACKEND_DIR/.env"
    export $(cat "$BACKEND_DIR/.env" | grep -v '^#' | xargs)
fi

# Default Redis URL if not set
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

QUEUES="${1:-document_processing graph_building default}"

echo "Starting RQ worker..."
echo "  Redis URL: $REDIS_URL"
echo "  Queues: $QUEUES"

# Start the worker with all required queues
cd "$BACKEND_DIR"
exec uv run rq worker \
    --url "$REDIS_URL" \
    --with-scheduler \
    $QUEUES
