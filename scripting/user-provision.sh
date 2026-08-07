#!/bin/bash
# user-provision.sh - automates user provisioning: create (single/bulk),
# reset password, lock, unlock, delete. Logs all actions, prints summary.
#
# Usage:
#   ./user-provision.sh create <username> <groupname> <sudo:yes|no>
#   ./user-provision.sh bulk <csv-file>
#   ./user-provision.sh reset <username>
#   ./user-provision.sh lock <username>
#   ./user-provision.sh unlock <username>
#   ./user-provision.sh delete <username> [--remove-home]
#
# CSV format (no header line): username,groupname,sudo(yes|no)

LOG_FILE="/var/log/user-provision.log"
SUCCESS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

log_action() {
    local MESSAGE="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $MESSAGE" >> "$LOG_FILE"
}

user_exists() {
    local UNAME="$1"
    id "$UNAME" &>/dev/null
}

create_user() {
    local UNAME="$1"
    local GROUPNAME="$2"
    local SUDO_FLAG="$3"

    if user_exists "$UNAME"; then
        echo "  [SKIP] $UNAME already exists"
        log_action "SKIP create: $UNAME already exists"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        return
    fi

    if ! getent group "$GROUPNAME" &>/dev/null; then
        groupadd "$GROUPNAME"
        log_action "Created group: $GROUPNAME"
    fi

    useradd -m -g "$GROUPNAME" "$UNAME"
    if [ $? -ne 0 ]; then
        echo "  [FAIL] $UNAME - useradd failed"
        log_action "FAIL create: $UNAME - useradd error"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    local TEMP_PASS
    TEMP_PASS=$(openssl rand -base64 9)
    echo "$UNAME:$TEMP_PASS" | chpasswd
    chage -d 0 "$UNAME"

    if [ "$SUDO_FLAG" = "yes" ]; then
        usermod -aG wheel "$UNAME"
        log_action "Granted sudo (wheel) to: $UNAME"
    fi

    echo "  [OK] $UNAME created (group: $GROUPNAME, sudo: $SUDO_FLAG, temp password: $TEMP_PASS)"
    log_action "SUCCESS create: $UNAME (group=$GROUPNAME sudo=$SUDO_FLAG)"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
}

provision_from_csv() {
    local CSV_FILE="$1"

    if [ ! -f "$CSV_FILE" ]; then
        echo "Error: CSV file '$CSV_FILE' not found"
        exit 1
    fi

    while IFS=',' read -r CSV_USER CSV_GROUP CSV_SUDO; do
        [ -z "$CSV_USER" ] && continue
        echo "Processing: $CSV_USER"
        create_user "$CSV_USER" "$CSV_GROUP" "$CSV_SUDO"
    done < "$CSV_FILE"
}

reset_password() {
    local UNAME="$1"

    if ! user_exists "$UNAME"; then
        echo "  [FAIL] $UNAME does not exist"
        log_action "FAIL reset: $UNAME does not exist"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    local TEMP_PASS
    TEMP_PASS=$(openssl rand -base64 9)
    echo "$UNAME:$TEMP_PASS" | chpasswd
    chage -d 0 "$UNAME"

    echo "  [OK] $UNAME password reset (temp password: $TEMP_PASS, must change at next login)"
    log_action "SUCCESS reset password: $UNAME"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
}

lock_account() {
    local UNAME="$1"

    if ! user_exists "$UNAME"; then
        echo "  [FAIL] $UNAME does not exist"
        log_action "FAIL lock: $UNAME does not exist"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    passwd -l "$UNAME" &>/dev/null
    echo "  [OK] $UNAME locked"
    log_action "SUCCESS lock: $UNAME"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
}

unlock_account() {
    local UNAME="$1"

    if ! user_exists "$UNAME"; then
        echo "  [FAIL] $UNAME does not exist"
        log_action "FAIL unlock: $UNAME does not exist"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    passwd -u "$UNAME" &>/dev/null
    echo "  [OK] $UNAME unlocked"
    log_action "SUCCESS unlock: $UNAME"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
}

delete_account() {
    local UNAME="$1"
    local REMOVE_HOME="$2"

    if ! user_exists "$UNAME"; then
        echo "  [FAIL] $UNAME does not exist"
        log_action "FAIL delete: $UNAME does not exist"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    if [ "$REMOVE_HOME" = "--remove-home" ]; then
        userdel -r "$UNAME"
        log_action "SUCCESS delete (with home): $UNAME"
    else
        userdel "$UNAME"
        log_action "SUCCESS delete (home kept): $UNAME"
    fi

    echo "  [OK] $UNAME deleted"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
}

print_summary() {
    echo "============================"
    echo "Summary:"
    echo "  Success: $SUCCESS_COUNT"
    echo "  Failed:  $FAIL_COUNT"
    echo "  Skipped: $SKIP_COUNT"
    echo "============================"
    log_action "Run summary - success=$SUCCESS_COUNT fail=$FAIL_COUNT skip=$SKIP_COUNT"
}

MODE="$1"

case "$MODE" in

    create)
        create_user "$2" "$3" "$4"
        print_summary
        ;;

    bulk)
        provision_from_csv "$2"
        print_summary
        ;;

    reset)
        reset_password "$2"
        print_summary
        ;;

    lock)
        lock_account "$2"
        print_summary
        ;;

    unlock)
        unlock_account "$2"
        print_summary
        ;;

    delete)
        delete_account "$2" "$3"
        print_summary
        ;;

    *)
        echo "Usage:"
        echo "  $0 create <username> <groupname> <sudo:yes|no>"
        echo "  $0 bulk <csv-file>"
        echo "  $0 reset <username>"
        echo "  $0 lock <username>"
        echo "  $0 unlock <username>"
        echo "  $0 delete <username> [--remove-home]"
        exit 1
        ;;
esac
SCRIPT_END
