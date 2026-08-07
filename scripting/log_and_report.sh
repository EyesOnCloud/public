#!/bin/bash

LOG_FILE="./compliance_$(date +%Y%m%d_%H%M%S).log"
PASS=0
FAIL=0

run_check() {
    local name="$1"
    local result="$2"
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [$result] $name" | tee -a "$LOG_FILE"
    [ "$result" = "PASS" ] && PASS=$((PASS+1)) || FAIL=$((FAIL+1))
}

echo "=== Running Compliance Checks ==="

if command -v getenforce &>/dev/null && [ "$(getenforce)" = "Enforcing" ]; then
    run_check "SELinux enforcing" "PASS"
else
    run_check "SELinux enforcing" "FAIL"
fi

if command -v firewall-cmd &>/dev/null && [ "$(systemctl is-active firewalld)" = "active" ]; then
    run_check "firewalld active" "PASS"
else
    run_check "firewalld active" "FAIL"
fi

echo
echo "=== Summary Report ==="
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ] && echo "Overall: COMPLIANT" || echo "Overall: NON-COMPLIANT"
echo "Log saved to: $LOG_FILE"
