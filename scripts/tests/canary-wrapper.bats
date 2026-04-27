#!/usr/bin/env bats
#
# BATS Tests for Canary Deployment Wrapper
# =========================================
#
# These tests validate the canary deployment wrapper with mocked
# threshold evaluations, ensuring safe production deployments.
#
# Prerequisites:
#   - BATS (Bash Automated Testing System)
#   - Install: npm install -g bats
#
# Run tests:
#   bats scripts/tests/canary-wrapper.bats

WRAPPER="scripts/canary-wrapper.sh"

setup() {
    # Set mock mode for all tests
    export MOCK_MODE=1
}

teardown() {
    # Cleanup
    unset MOCK_MODE MOCK_ERROR_RATIO MOCK_LATENCY_RATIO
}

@test "wrapper script exists and is executable" {
    [ -f "$WRAPPER" ]
    [ -x "$WRAPPER" ]
}

@test "shows help message with --help flag" {
    run bash "$WRAPPER" --help
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Usage:" ]]
    [[ "$output" =~ "--service" ]]
}

@test "fails with missing required arguments" {
    run bash "$WRAPPER" --service test
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Missing required arguments" ]]
}

@test "accepts all required arguments" {
    export MOCK_ERROR_RATIO=0.8
    export MOCK_LATENCY_RATIO=0.9
    
    run bash "$WRAPPER" \
        --service recommendationservice \
        --baseline ghcr.io/user/app:v1.0 \
        --canary ghcr.io/user/app:v1.1
    
    [ "$status" -eq 0 ]
    [[ "$output" =~ "MOCK MODE" ]]
}

@test "PROCEED decision when metrics are healthy (low error, low latency)" {
    export MOCK_ERROR_RATIO=0.8   # 80% of baseline (good)
    export MOCK_LATENCY_RATIO=0.9 # 90% of baseline (good)
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    [ "$status" -eq 0 ]
    [[ "$output" =~ "PROCEED" ]]
    [[ "$output" =~ "Mock deployment: SUCCESS" ]]
}

@test "ROLLBACK decision when error ratio exceeds threshold" {
    export MOCK_ERROR_RATIO=1.5   # 150% of baseline (bad - exceeds 1.2x)
    export MOCK_LATENCY_RATIO=0.9 # Latency is fine
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    [ "$status" -eq 1 ]
    [[ "$output" =~ "ROLLBACK" ]]
    [[ "$output" =~ "Error ratio exceeds threshold" ]]
}

@test "ROLLBACK decision when latency ratio exceeds threshold" {
    export MOCK_ERROR_RATIO=0.9   # Error rate is fine
    export MOCK_LATENCY_RATIO=1.8 # 180% of baseline (bad - exceeds 1.5x)
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    [ "$status" -eq 1 ]
    [[ "$output" =~ "ROLLBACK" ]]
    [[ "$output" =~ "Latency ratio exceeds threshold" ]]
}

@test "ROLLBACK decision when both metrics exceed thresholds" {
    export MOCK_ERROR_RATIO=1.5   # Bad
    export MOCK_LATENCY_RATIO=2.0 # Bad
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    [ "$status" -eq 1 ]
    [[ "$output" =~ "ROLLBACK" ]]
}

@test "boundary test: error ratio exactly at threshold" {
    export MOCK_ERROR_RATIO=1.2   # Exactly at 1.2x threshold
    export MOCK_LATENCY_RATIO=0.9
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    # At boundary, should still pass (not greater than)
    [ "$status" -eq 0 ]
}

@test "boundary test: latency ratio exactly at threshold" {
    export MOCK_ERROR_RATIO=0.9
    export MOCK_LATENCY_RATIO=1.5 # Exactly at 1.5x threshold
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    # At boundary, should still pass
    [ "$status" -eq 0 ]
}

@test "validates service name is passed through" {
    export MOCK_ERROR_RATIO=0.8
    export MOCK_LATENCY_RATIO=0.9
    
    run bash "$WRAPPER" \
        --service my-special-service \
        --baseline v1.0 \
        --canary v1.1
    
    [ "$status" -eq 0 ]
    [[ "$output" =~ "my-special-service" ]]
}

@test "validates baseline image is passed through" {
    export MOCK_ERROR_RATIO=0.8
    export MOCK_LATENCY_RATIO=0.9
    
    run bash "$WRAPPER" \
        --service test \
        --baseline ghcr.io/myrepo/app:baseline-123 \
        --canary v1.1
    
    [ "$status" -eq 0 ]
    [[ "$output" =~ "ghcr.io/myrepo/app:baseline-123" ]]
}

@test "validates canary image is passed through" {
    export MOCK_ERROR_RATIO=0.8
    export MOCK_LATENCY_RATIO=0.9
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary ghcr.io/myrepo/app:canary-456
    
    [ "$status" -eq 0 ]
    [[ "$output" =~ "ghcr.io/myrepo/app:canary-456" ]]
}

@test "reports threshold values in output" {
    export MOCK_ERROR_RATIO=1.0
    export MOCK_LATENCY_RATIO=1.0
    
    run bash "$WRAPPER" \
        --service test \
        --baseline v1.0 \
        --canary v1.1
    
    [ "$status" -eq 0 ]
    [[ "$output" =~ "threshold: 1.2" ]]  # Error rate threshold
    [[ "$output" =~ "threshold: 1.5" ]]  # Latency threshold
}
