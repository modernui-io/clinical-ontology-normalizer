#!/bin/bash
# Test watcher for safe refactoring
# Usage: ./scripts/test_watch.sh [backend|frontend|all] [pattern]

set -e

MODE=${1:-all}
PATTERN=${2:-}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

run_backend_tests() {
    echo -e "${YELLOW}Running backend tests...${NC}"
    cd /Users/alexstinard/projects/brainstorm/jan-14-2026/backend
    if [ -n "$PATTERN" ]; then
        python3 -m pytest tests/ -k "$PATTERN" --no-cov -q --tb=short 2>&1
    else
        python3 -m pytest tests/ --no-cov -q --tb=short 2>&1
    fi
}

run_frontend_tests() {
    echo -e "${YELLOW}Running frontend tests...${NC}"
    cd /Users/alexstinard/projects/brainstorm/jan-14-2026/frontend
    if [ -n "$PATTERN" ]; then
        npm test -- --testPathPattern="$PATTERN" --watchAll=false 2>&1
    else
        npm test -- --watchAll=false 2>&1
    fi
}

check_typescript() {
    echo -e "${YELLOW}Type checking frontend...${NC}"
    cd /Users/alexstinard/projects/brainstorm/jan-14-2026/frontend
    npx tsc --noEmit 2>&1
}

check_python_types() {
    echo -e "${YELLOW}Type checking backend...${NC}"
    cd /Users/alexstinard/projects/brainstorm/jan-14-2026/backend
    python3 -m mypy app/ --ignore-missing-imports --no-error-summary 2>&1 | head -20 || true
}

echo "=========================================="
echo "  Test Runner - Mode: $MODE"
echo "=========================================="

case $MODE in
    backend)
        run_backend_tests
        ;;
    frontend)
        check_typescript
        run_frontend_tests
        ;;
    all)
        run_backend_tests
        check_typescript
        run_frontend_tests
        ;;
    quick)
        # Fast smoke test
        cd /Users/alexstinard/projects/brainstorm/jan-14-2026/backend
        python3 -m pytest tests/ -m "unit or smoke" --no-cov -q --tb=line -x 2>&1
        ;;
    *)
        echo "Usage: $0 [backend|frontend|all|quick] [pattern]"
        exit 1
        ;;
esac

echo -e "${GREEN}✓ All tests passed${NC}"
