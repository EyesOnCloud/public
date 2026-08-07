#!/bin/bash

# pkg-check.sh
# Checks whether a package is installed, installs it if missing,
# and reports its systemd service status.

# Usage: ./pkg-check.sh <package-name>

PACKAGE="$1"

if [ -z "$PACKAGE" ]; then
    echo "Error: no package name provided"
    echo "Usage: $0 <package-name>"
    exit 1
fi

echo "Checking package: $PACKAGE"

# -----------------------------------
# Check package installation
# -----------------------------------

if rpm -q "$PACKAGE" &>/dev/null; then
    echo "  [OK] $PACKAGE is already installed"
else
    echo "  [MISSING] $PACKAGE not installed, installing now..."

    dnf install -y "$PACKAGE" &>/dev/null

    if rpm -q "$PACKAGE" &>/dev/null; then
        echo "  [OK] $PACKAGE installed successfully"
    else
        echo "  [FAIL] $PACKAGE installation failed"
        exit 1
    fi
fi


# -----------------------------------
# Determine systemd service name
# -----------------------------------

SERVICE="$PACKAGE"

case "$PACKAGE" in
    chrony)
        SERVICE="chronyd"
        ;;
esac


# -----------------------------------
# Check service status
# -----------------------------------

if systemctl list-unit-files --type=service | grep -q "^${SERVICE}.service"; then

    if systemctl is-enabled "$SERVICE" &>/dev/null; then
        echo "  [OK] $SERVICE service is enabled"
    else
        echo "  [WARN] $SERVICE service is NOT enabled"
    fi


    if systemctl is-active "$SERVICE" &>/dev/null; then
        echo "  [OK] $SERVICE service is running"
    else
        echo "  [WARN] $SERVICE service is NOT running"
    fi

else

    echo "  [INFO] $PACKAGE has no matching systemd service — skipping service check"

fi


echo "Done."

exit 0
