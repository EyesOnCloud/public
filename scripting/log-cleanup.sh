#!/bin/bash
# log-cleanup.sh - scans directories for log files, rotates by size/age,
# compresses, enforces retention, logs everything, prints summary.
#
# Usage: ./log-cleanup.sh <dir1> [dir2] [dir3] ...
# Config below can be edited directly or overridden via environment variables.

SIZE_THRESHOLD_MB="${SIZE_THRESHOLD_MB:-10}"
AGE_THRESHOLD_DAYS="${AGE_THRESHOLD_DAYS:-7}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
EXCLUDE_LIST=("audit.log" "important-do-not-touch.log")
LOG_FILE="/var/log/log-cleanup.log"
MIN_FREE_MB=100

SCANNED=0
ROTATED=0
COMPRESSED=0
DELETED=0
SKIPPED=0
SPACE_RECLAIMED_KB=0

log_action() {
    local MESSAGE="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $MESSAGE" >> "$LOG_FILE"
}

check_disk_space() {
    local TARGET_DIR="$1"
    local AVAIL_MB
    AVAIL_MB=$(df -Pm "$TARGET_DIR" | awk 'NR==2 {print $4}')

    if [ "$AVAIL_MB" -lt "$MIN_FREE_MB" ]; then
        return 1
    else
        return 0
    fi
}

is_excluded() {
    local FILENAME="$1"
    local BASENAME
    BASENAME=$(basename "$FILENAME")

    for EXCLUDED in "${EXCLUDE_LIST[@]}"; do
        if [ "$BASENAME" = "$EXCLUDED" ]; then
            return 0
        fi
    done
    return 1
}

rotate_file() {
    local FILE="$1"
    local TIMESTAMP
    TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
    local ROTATED_NAME="${FILE}.${TIMESTAMP}"

    mv "$FILE" "$ROTATED_NAME"
    touch "$FILE"
    chmod 640 "$FILE"

    log_action "ROTATED: $FILE -> $ROTATED_NAME"
    ROTATED=$((ROTATED + 1))

    compress_file "$ROTATED_NAME"
}

compress_file() {
    local FILE="$1"
    local ORIG_SIZE_KB
    ORIG_SIZE_KB=$(du -k "$FILE" | cut -f1)

    gzip "$FILE"

    local NEW_SIZE_KB
    NEW_SIZE_KB=$(du -k "${FILE}.gz" | cut -f1)
    local SAVED=$((ORIG_SIZE_KB - NEW_SIZE_KB))

    SPACE_RECLAIMED_KB=$((SPACE_RECLAIMED_KB + SAVED))
    log_action "COMPRESSED: ${FILE}.gz (saved ${SAVED}KB)"
    COMPRESSED=$((COMPRESSED + 1))
}

cleanup_old_archives() {
    local TARGET_DIR="$1"

    while IFS= read -r OLD_ARCHIVE; do
        [ -z "$OLD_ARCHIVE" ] && continue
        local SIZE_KB
        SIZE_KB=$(du -k "$OLD_ARCHIVE" | cut -f1)
        rm -f "$OLD_ARCHIVE"
        SPACE_RECLAIMED_KB=$((SPACE_RECLAIMED_KB + SIZE_KB))
        log_action "DELETED (past retention): $OLD_ARCHIVE"
        DELETED=$((DELETED + 1))
    done < <(find "$TARGET_DIR" -name "*.log.*.gz" -mtime "+${RETENTION_DAYS}" 2>/dev/null)
}

process_directory() {
    local TARGET_DIR="$1"

    if [ ! -d "$TARGET_DIR" ]; then
        echo "  [FAIL] Directory not found: $TARGET_DIR"
        log_action "FAIL: directory not found: $TARGET_DIR"
        return
    fi

    if ! check_disk_space "$TARGET_DIR"; then
        echo "  [FAIL] Insufficient free space near $TARGET_DIR, skipping cleanup"
        log_action "FAIL: insufficient disk space for $TARGET_DIR"
        return
    fi

    echo "Processing directory: $TARGET_DIR"

    while IFS= read -r LOGFILE; do
        [ -z "$LOGFILE" ] && continue
        SCANNED=$((SCANNED + 1))

        if is_excluded "$LOGFILE"; then
            echo "  [SKIP] $LOGFILE (excluded)"
            log_action "SKIP (excluded): $LOGFILE"
            SKIPPED=$((SKIPPED + 1))
            continue
        fi

        local SIZE_MB
        SIZE_MB=$(du -m "$LOGFILE" | cut -f1)

        local AGE_DAYS
        AGE_DAYS=$(( ( $(date +%s) - $(stat -c %Y "$LOGFILE") ) / 86400 ))

        if [ "$SIZE_MB" -ge "$SIZE_THRESHOLD_MB" ] || [ "$AGE_DAYS" -ge "$AGE_THRESHOLD_DAYS" ]; then
            echo "  [ROTATE] $LOGFILE (size=${SIZE_MB}MB age=${AGE_DAYS}d)"
            rotate_file "$LOGFILE"
        else
            echo "  [OK] $LOGFILE (size=${SIZE_MB}MB age=${AGE_DAYS}d) — below thresholds"
        fi

    done < <(find "$TARGET_DIR" -maxdepth 1 -name "*.log" -type f 2>/dev/null)

    cleanup_old_archives "$TARGET_DIR"
}

print_summary() {
    local RECLAIMED_MB=$((SPACE_RECLAIMED_KB / 1024))
    echo "============================"
    echo "Summary:"
    echo "  Scanned:    $SCANNED"
    echo "  Rotated:    $ROTATED"
    echo "  Compressed: $COMPRESSED"
    echo "  Deleted:    $DELETED"
    echo "  Skipped:    $SKIPPED"
    echo "  Space reclaimed: ${RECLAIMED_MB}MB"
    echo "============================"
    log_action "Run summary - scanned=$SCANNED rotated=$ROTATED compressed=$COMPRESSED deleted=$DELETED skipped=$SKIPPED reclaimed=${RECLAIMED_MB}MB"
}

if [ "$#" -eq 0 ]; then
    echo "Error: no directories provided"
    echo "Usage: $0 <dir1> [dir2] [dir3] ..."
    exit 1
fi

echo "=== Log Rotation & Cleanup ==="
echo "Size threshold: ${SIZE_THRESHOLD_MB}MB | Age threshold: ${AGE_THRESHOLD_DAYS}d | Retention: ${RETENTION_DAYS}d"
echo ""

for DIR in "$@"; do
    process_directory "$DIR"
done

print_summary
exit 0
SCRIPT_END
