#!/usr/bin/env bash
# CISO-10: Local Security Scan Script
# Run all security checks locally before pushing.
#
# Usage:
#   ./backend/scripts/security_scan.sh          # Run all checks
#   ./backend/scripts/security_scan.sh bandit    # Run only Bandit SAST
#   ./backend/scripts/security_scan.sh pip-audit # Run only pip-audit
#   ./backend/scripts/security_scan.sh npm-audit # Run only npm audit
#   ./backend/scripts/security_scan.sh secrets   # Run only secret detection
#   ./backend/scripts/security_scan.sh trivy     # Run only Trivy container scan

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

# Track results
PASSED=0
FAILED=0
SKIPPED=0
RESULTS=()

print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

print_result() {
    local name="$1"
    local status="$2"
    if [ "$status" -eq 0 ]; then
        echo -e "  ${GREEN}PASS${NC}  $name"
        PASSED=$((PASSED + 1))
        RESULTS+=("PASS: $name")
    elif [ "$status" -eq 2 ]; then
        echo -e "  ${YELLOW}SKIP${NC}  $name (tool not installed)"
        SKIPPED=$((SKIPPED + 1))
        RESULTS+=("SKIP: $name")
    else
        echo -e "  ${RED}FAIL${NC}  $name"
        FAILED=$((FAILED + 1))
        RESULTS+=("FAIL: $name")
    fi
}

check_command() {
    command -v "$1" &>/dev/null
}

# ──────────────────────────────────────────────
# 1. Bandit SAST
# ──────────────────────────────────────────────
run_bandit() {
    print_header "1/5  Bandit SAST (Python)"

    if ! check_command bandit; then
        echo -e "${YELLOW}bandit not installed. Install with: pip install bandit[toml]${NC}"
        print_result "Bandit SAST" 2
        return
    fi

    echo "Scanning backend/app/ for medium+ severity issues..."
    if bandit -r "$BACKEND_DIR/app/" \
        --severity-level medium \
        --confidence-level medium \
        -f screen \
        --quiet; then
        print_result "Bandit SAST" 0
    else
        print_result "Bandit SAST" 1
    fi
}

# ──────────────────────────────────────────────
# 2. pip-audit
# ──────────────────────────────────────────────
run_pip_audit() {
    print_header "2/5  pip-audit (Python Dependencies)"

    if ! check_command pip-audit; then
        echo -e "${YELLOW}pip-audit not installed. Install with: pip install pip-audit${NC}"
        print_result "pip-audit" 2
        return
    fi

    echo "Auditing Python dependencies for known vulnerabilities..."
    local req_file
    req_file=$(mktemp)

    # Try to export frozen requirements
    if check_command uv; then
        (cd "$BACKEND_DIR" && uv pip freeze > "$req_file" 2>/dev/null) || \
        (cd "$BACKEND_DIR" && uv run pip freeze > "$req_file" 2>/dev/null) || true
    elif check_command pip; then
        pip freeze > "$req_file" 2>/dev/null || true
    fi

    if [ -s "$req_file" ]; then
        if pip-audit --requirement "$req_file" --desc; then
            print_result "pip-audit" 0
        else
            print_result "pip-audit" 1
        fi
    else
        echo -e "${YELLOW}Could not generate requirements list. Skipping.${NC}"
        print_result "pip-audit" 2
    fi

    rm -f "$req_file"
}

# ──────────────────────────────────────────────
# 3. npm audit
# ──────────────────────────────────────────────
run_npm_audit() {
    print_header "3/5  npm audit (Frontend Dependencies)"

    if ! check_command npm; then
        echo -e "${YELLOW}npm not installed. Install Node.js to use npm audit.${NC}"
        print_result "npm audit" 2
        return
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo "Installing frontend dependencies first..."
        (cd "$FRONTEND_DIR" && npm ci --silent)
    fi

    echo "Auditing npm packages for known vulnerabilities..."
    if (cd "$FRONTEND_DIR" && npm audit --audit-level=high); then
        print_result "npm audit" 0
    else
        print_result "npm audit" 1
    fi
}

# ──────────────────────────────────────────────
# 4. Secret Detection
# ──────────────────────────────────────────────
run_secrets() {
    print_header "4/5  Secret Detection"

    # Try gitleaks first, fall back to detect-secrets
    if check_command gitleaks; then
        echo "Running Gitleaks..."
        if (cd "$REPO_ROOT" && gitleaks detect --source . --verbose); then
            print_result "Secret Detection (Gitleaks)" 0
        else
            print_result "Secret Detection (Gitleaks)" 1
        fi
    elif check_command detect-secrets; then
        echo "Running detect-secrets..."
        if (cd "$REPO_ROOT" && detect-secrets scan --all-files --force-use-all-plugins | \
            python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', {})
total = sum(len(v) for v in results.values())
if total > 0:
    print(f'Found {total} potential secrets in {len(results)} files:')
    for f, findings in results.items():
        for finding in findings:
            print(f'  {f}:{finding[\"line_number\"]} - {finding[\"type\"]}')
    sys.exit(1)
else:
    print('No secrets detected.')
"); then
            print_result "Secret Detection (detect-secrets)" 0
        else
            print_result "Secret Detection (detect-secrets)" 1
        fi
    else
        echo -e "${YELLOW}Neither gitleaks nor detect-secrets installed.${NC}"
        echo "  Install gitleaks:       brew install gitleaks (macOS) or see https://github.com/gitleaks/gitleaks"
        echo "  Install detect-secrets: pip install detect-secrets"
        print_result "Secret Detection" 2
    fi
}

# ──────────────────────────────────────────────
# 5. Trivy Container Scan
# ──────────────────────────────────────────────
run_trivy() {
    print_header "5/5  Trivy Container Scan (Backend Image)"

    if ! check_command trivy; then
        echo -e "${YELLOW}trivy not installed. Install with: brew install trivy (macOS) or see https://aquasecurity.github.io/trivy${NC}"
        print_result "Trivy Container Scan" 2
        return
    fi

    if ! check_command docker; then
        echo -e "${YELLOW}docker not available. Falling back to filesystem scan.${NC}"
        echo "Running Trivy filesystem scan on backend/..."
        if trivy fs "$BACKEND_DIR" --severity HIGH,CRITICAL --exit-code 1; then
            print_result "Trivy Filesystem Scan" 0
        else
            print_result "Trivy Filesystem Scan" 1
        fi
        return
    fi

    echo "Building backend image for scanning..."
    local image_tag="security-scan/backend:local"

    if docker build -t "$image_tag" "$BACKEND_DIR" -q; then
        echo "Scanning container image..."
        if trivy image "$image_tag" \
            --severity HIGH,CRITICAL \
            --ignore-unfixed \
            --exit-code 1; then
            print_result "Trivy Container Scan" 0
        else
            print_result "Trivy Container Scan" 1
        fi
        # Cleanup
        docker rmi "$image_tag" &>/dev/null || true
    else
        echo -e "${YELLOW}Docker build failed. Falling back to filesystem scan.${NC}"
        if trivy fs "$BACKEND_DIR" --severity HIGH,CRITICAL --exit-code 1; then
            print_result "Trivy Filesystem Scan" 0
        else
            print_result "Trivy Filesystem Scan" 1
        fi
    fi
}

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Security Scan Summary${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    for r in "${RESULTS[@]}"; do
        if [[ "$r" == PASS:* ]]; then
            echo -e "  ${GREEN}$r${NC}"
        elif [[ "$r" == FAIL:* ]]; then
            echo -e "  ${RED}$r${NC}"
        else
            echo -e "  ${YELLOW}$r${NC}"
        fi
    done
    echo ""
    echo -e "  Passed: ${GREEN}$PASSED${NC}  Failed: ${RED}$FAILED${NC}  Skipped: ${YELLOW}$SKIPPED${NC}"
    echo ""

    if [ "$FAILED" -gt 0 ]; then
        echo -e "${RED}Security scan completed with failures. Fix issues before pushing.${NC}"
        exit 1
    elif [ "$SKIPPED" -gt 0 ]; then
        echo -e "${YELLOW}Security scan completed with skipped checks. Install missing tools for full coverage.${NC}"
        exit 0
    else
        echo -e "${GREEN}All security scans passed.${NC}"
        exit 0
    fi
}

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
main() {
    echo -e "${BLUE}Clinical Ontology Normalizer - Security Scan${NC}"
    echo "Repo root: $REPO_ROOT"
    echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

    local target="${1:-all}"

    case "$target" in
        bandit)
            run_bandit
            ;;
        pip-audit)
            run_pip_audit
            ;;
        npm-audit)
            run_npm_audit
            ;;
        secrets)
            run_secrets
            ;;
        trivy)
            run_trivy
            ;;
        all)
            run_bandit
            run_pip_audit
            run_npm_audit
            run_secrets
            run_trivy
            ;;
        *)
            echo "Usage: $0 [bandit|pip-audit|npm-audit|secrets|trivy|all]"
            exit 1
            ;;
    esac

    print_summary
}

main "$@"
