#!/bin/bash

# pkg-check.sh - checks if a package is installed, installs if missing,

# and reports its systemd service status.

# Usage: ./pkg-check.sh <package-name>



PACKAGE="$1"



if [ -z "$PACKAGE" ]; then

    echo "Error: no package name provided"

    echo "Usage: $0 <package-name>"

    exit 1

fi



echo "Checking package: $PACKAGE"



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



if systemctl list-unit-files | grep -q "^${PACKAGE}.service"; then



    if systemctl is-enabled "$PACKAGE" &>/dev/null; then

        echo "  [OK] $PACKAGE service is enabled"

    else

        echo "  [WARN] $PACKAGE service is NOT enabled"

    fi



    if systemctl is-active "$PACKAGE" &>/dev/null; then

        echo "  [OK] $PACKAGE service is running"

    else

        echo "  [WARN] $PACKAGE service is NOT running"

    fi



else

    echo "  [INFO] $PACKAGE has no matching systemd service — skipping service check"

fi



echo "Done."

exit 0
