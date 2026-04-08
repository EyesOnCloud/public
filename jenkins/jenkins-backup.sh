#!/bin/bash

BACKUP_DIR="/opt/jenkins-backup"
JENKINS_HOME="/var/lib/jenkins"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/jenkins-backup-${TIMESTAMP}.tar.gz"
KEEP_DAYS=7
LOG_FILE="${BACKUP_DIR}/backup.log"

echo "[$(date)] Starting Jenkins backup" >> "$LOG_FILE"

# Stop Jenkins
systemctl stop jenkins
echo "[$(date)] Jenkins stopped" >> "$LOG_FILE"

# Create backup
tar -czf "$BACKUP_FILE" \
  --exclude="${JENKINS_HOME}/workspace" \
  --exclude="${JENKINS_HOME}/updates" \
  --exclude="${JENKINS_HOME}/cache" \
  --exclude="${JENKINS_HOME}/logs" \
  -C "$JENKINS_HOME" .

if [ $? -eq 0 ]; then
  echo "[$(date)] Backup created: $BACKUP_FILE ($(du -sh $BACKUP_FILE | cut -f1))" >> "$LOG_FILE"
else
  echo "[$(date)] ERROR: Backup failed" >> "$LOG_FILE"
  systemctl start jenkins
  exit 1
fi

# Start Jenkins
systemctl start jenkins
echo "[$(date)] Jenkins started" >> "$LOG_FILE"

# Remove backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "jenkins-backup-*.tar.gz" -mtime +${KEEP_DAYS} -delete
echo "[$(date)] Cleaned up backups older than ${KEEP_DAYS} days" >> "$LOG_FILE"

echo "[$(date)] Backup complete" >> "$LOG_FILE"
