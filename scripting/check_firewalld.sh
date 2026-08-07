#!/bin/bash

echo "=== Firewalld Status Check ==="

if ! command -v firewall-cmd &>/dev/null; then
    echo "[SKIP] firewalld not installed"
    exit 0
fi

ACTIVE=$(systemctl is-active firewalld)
ENABLED=$(systemctl is-enabled firewalld)
ZONE=$(firewall-cmd --get-default-zone)
SERVICES=$(firewall-cmd --zone="$ZONE" --list-services)
PORTS=$(firewall-cmd --zone="$ZONE" --list-ports)

echo "Active state    : $ACTIVE"
echo "Enabled state   : $ENABLED"
echo "Default zone    : $ZONE"
echo "Allowed services: $SERVICES"
echo "Open ports      : $PORTS"

[ "$ACTIVE" = "active" ] && echo "[PASS] firewalld is running" || echo "[FAIL] firewalld is not running"
[ "$ENABLED" = "enabled" ] && echo "[PASS] firewalld enabled at boot" || echo "[FAIL] firewalld not enabled at boot"
