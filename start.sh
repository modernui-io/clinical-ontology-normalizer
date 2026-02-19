#!/bin/bash
# Start the Clinical Ontology Normalizer
# Usage: ./start.sh

set -e

cd "$(dirname "$0")"

echo "Starting Docker stack (backend, databases, worker)..."
docker compose up -d

echo "Waiting for backend to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:8080/api/v1/health > /dev/null 2>&1; then
    echo "Backend is ready!"
    break
  fi
  sleep 1
done

echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo "  App is running!"
echo "  Open http://localhost:3000 in browser"
echo "  Press Ctrl+C to stop frontend"
echo "========================================="
echo ""

wait $FRONTEND_PID
