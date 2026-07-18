#!/usr/bin/env bash
#
# Canary Deployment Wrapper with Mock Support
# ============================================
#
# This wrapper provides a resilient automation layer around canary-deploy.py
# with mocked metric threshold evaluation for testing and CI/CD validation.
#
# Features:
# - Pre-flight threshold validation
# - Mock mode for testing without real Prometheus/K8s
# - Exit code propagation for pipeline integration
# - Detailed error reporting
#
# Usage:
# ./canary-wrapper.sh --service recommendationservice \
# --baseline ghcr.io/user/app:v1.0 \
# --canary ghcr.io/user/app:v1.1
#
# # Mock mode (for testing):
# MOCK_MODE=1 MOCK_ERROR_RATIO=0.8 MOCK_LATENCY_RATIO=0.9 \
# ./canary-wrapper.sh --service test --baseline v1 --canary v2

set -euo pipefail

# Color output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# Thresholds (must match Python script)
readonly ERROR_RATE_THRESHOLD=1.2  # 20% worse than baseline
readonly LATENCY_THRESHOLD=1.5     # 50% slower than baseline

# Mock mode environment variables
MOCK_MODE="${MOCK_MODE:-0}"
MOCK_ERROR_RATIO="${MOCK_ERROR_RATIO:-0.8}"
MOCK_LATENCY_RATIO="${MOCK_LATENCY_RATIO:-0.9}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

check_dependencies() {
    local missing=0
    
    if [[ "$MOCK_MODE" == "0" ]]; then
        for cmd in python3 kubectl; do
            if ! command -v "$cmd" &> /dev/null; then
                log_error "Required command not found: $cmd"
                missing=1
            fi
        done
    fi
    
    return "$missing"
}

validate_thresholds() {
    local error_ratio="$1"
    local latency_ratio="$2"
    
    log_info "Validating thresholds..."
    log_info "  Error ratio: ${error_ratio}x (threshold: ${ERROR_RATE_THRESHOLD}x)"
    log_info "  Latency ratio: ${latency_ratio}x (threshold: ${LATENCY_THRESHOLD}x)"
    
    # Use awk for floating point comparison
    if awk -v val="$error_ratio" -v thresh="$ERROR_RATE_THRESHOLD" \
           'BEGIN { exit (val > thresh) ? 0 : 1 }'; then
        log_error "ROLLBACK: Error ratio exceeds threshold"
        return 1
    fi
    
    if awk -v val="$latency_ratio" -v thresh="$LATENCY_THRESHOLD" \
           'BEGIN { exit (val > thresh) ? 0 : 1 }'; then
        log_error "ROLLBACK: Latency ratio exceeds threshold"
        return 1
    fi
    
    log_info "PROCEED: All thresholds passed"
    return 0
}

mock_canary_deployment() {
    local service="$1"
    local baseline="$2"
    local canary="$3"
    
    log_info "=== MOCK MODE ==="
    log_info "Service: $service"
    log_info "Baseline: $baseline"
    log_info "Canary: $canary"
    log_info ""
    
    log_info "Simulating deployment..."
    sleep 1
    
    log_info "Simulating metric collection..."
    sleep 1
    
    log_info "Evaluating canary with mocked metrics:"
    
    if validate_thresholds "$MOCK_ERROR_RATIO" "$MOCK_LATENCY_RATIO"; then
        log_info "Mock deployment: SUCCESS"
        return 0
    else
        log_error "Mock deployment: ROLLBACK"
        return 1
    fi
}

run_canary_deployment() {
    local service="$1"
    local baseline="$2"
    local canary="$3"
    shift 3
    local extra_args=("$@")
    
    log_info "Executing canary deployment via Python script..."
    
    # Run the actual Python canary deployment
    if python3 "$(dirname "$0")/canary-deploy.py" \
        --service "$service" \
        --baseline "$baseline" \
        --canary "$canary" \
        "${extra_args[@]}"; then
        log_info "Canary deployment completed successfully"
        return 0
    else
        log_error "Canary deployment failed"
        return 1
    fi
}

show_usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --service SERVICE       Service name (required)
  --baseline IMAGE        Baseline Docker image (required)
  --canary IMAGE          Canary Docker image (required)
  --namespace NS          Kubernetes namespace (default: citrus)
  --prometheus URL        Prometheus URL (default: http://localhost:9090)
  --duration SECONDS      Monitoring duration (default: 180)
  -h, --help              Show this help message

Environment Variables (Mock Mode):
  MOCK_MODE=1             Enable mock mode (no real deployment)
  MOCK_ERROR_RATIO=0.8    Simulated error ratio (default: 0.8)
  MOCK_LATENCY_RATIO=0.9  Simulated latency ratio (default: 0.9)

Examples:
  # Real deployment
  $0 --service recommendationservice \\
     --baseline ghcr.io/user/app:v1.0 \\
     --canary ghcr.io/user/app:v1.1

  # Mock deployment for testing
  MOCK_MODE=1 MOCK_ERROR_RATIO=1.5 $0 \\
     --service test --baseline v1 --canary v2
EOF
}

main() {
    local service=""
    local baseline=""
    local canary=""
    local extra_args=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --service)
                service="$2"
                shift 2
                ;;
            --baseline)
                baseline="$2"
                shift 2
                ;;
            --canary)
                canary="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                extra_args+=("$1")
                shift
                ;;
        esac
    done
    
    # Validate required arguments
    if [[ -z "$service" ]] || [[ -z "$baseline" ]] || [[ -z "$canary" ]]; then
        log_error "Missing required arguments"
        show_usage
        exit 1
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi
    
    # Execute deployment (mock or real)
    if [[ "$MOCK_MODE" == "1" ]]; then
        mock_canary_deployment "$service" "$baseline" "$canary"
    else
        run_canary_deployment "$service" "$baseline" "$canary" "${extra_args[@]}"
    fi
}

main "$@"
