#!/bin/bash

echo "=== Compliance Policy Diff ==="

REQUIRED_PORTS=("22/tcp" "80/tcp" "443/tcp")
FORBIDDEN_PORTS=("23/tcp" "21/tcp")

if ! command -v firewall-cmd &>/dev/null; then
    echo "[SKIP] firewalld not installed"
    exit 0
fi

ZONE=$(firewall-cmd --get-default-zone)
OPEN_PORTS=$(firewall-cmd --zone="$ZONE" --list-ports)

echo "Currently open ports: ${OPEN_PORTS:-none}"
echo

for port in "${REQUIRED_PORTS[@]}"; do
    if echo " $OPEN_PORTS " | grep -qw "$port"; then
        echo "[PASS] Required port $port is open"
    else
        echo "[FAIL] Required port $port is missing -> firewall-cmd --add-port=$port --permanent"
    fi
done

for port in "${FORBIDDEN_PORTS[@]}"; do
    if echo " $OPEN_PORTS " | grep -qw "$port"; then
        echo "[FAIL] Forbidden port $port is OPEN -> firewall-cmd --remove-port=$port --permanent"
    else
        echo "[PASS] Forbidden port $port is correctly closed"
    fi
done
