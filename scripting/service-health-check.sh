#!/bin/bash
# service-health-check.sh - checks enabled/active status for a list
# of critical services and reports pass/fail.

SERVICES=("sshd" "firewalld" "chronyd" "crond")
FAIL_COUNT=0

echo "=== Service Health Check ==="

for svc in "${SERVICES[@]}"; do

    ENABLED="FAIL"
    ACTIVE="FAIL"

    if systemctl is-enabled "$svc" &>/dev/null; then
        ENABLED="OK"
    fi

    if systemctl is-active "$svc" &>/dev/null; then
        ACTIVE="OK"
    fi

    if [ "$ENABLED" = "OK" ] && [ "$ACTIVE" = "OK" ]; then
        echo "[PASS] $svc  (enabled: $ENABLED, active: $ACTIVE)"
    else
        echo "[FAIL] $svc  (enabled: $ENABLED, active: $ACTIVE)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

done

echo "============================"

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "Overall: ALL SERVICES HEALTHY"
    exit 0
else
    echo "Overall: $FAIL_COUNT SERVICE(S) NEED ATTENTION"
    exit 1
fi
EOF
