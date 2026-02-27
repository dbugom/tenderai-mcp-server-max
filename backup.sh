#!/usr/bin/env bash
# TenderAI — Backup script with retention
# Usage: ./backup.sh [backup_dir] [retention_days]
# Example: ./backup.sh /backups/tenderai 30
# Recommended: Run daily via cron

set -euo pipefail

INSTALL_DIR="/opt/tenderai"
BACKUP_DIR="${1:-/backups/tenderai}"
RETENTION_DAYS="${2:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="tenderai_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "=== TenderAI Backup — $(date) ==="

# Create backup directory
mkdir -p "$BACKUP_PATH"

# --- Database backup (online, using SQLite .backup) ---
echo "[1/3] Backing up database..."
if [ -f "$INSTALL_DIR/db/tenderai.db" ]; then
    sqlite3 "$INSTALL_DIR/db/tenderai.db" ".backup '$BACKUP_PATH/tenderai.db'"
    echo "  Database backed up."
else
    echo "  No database found — skipping."
fi

# --- Data directory ---
echo "[2/3] Backing up data directory..."
if [ -d "$INSTALL_DIR/data" ]; then
    tar czf "$BACKUP_PATH/data.tar.gz" -C "$INSTALL_DIR" data/
    echo "  Data directory backed up."
else
    echo "  No data directory found — skipping."
fi

# --- Configuration ---
echo "[3/3] Backing up configuration..."
if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" "$BACKUP_PATH/.env"
    chmod 600 "$BACKUP_PATH/.env"
    echo "  Configuration backed up."
fi

# --- Compress the full backup ---
cd "$BACKUP_DIR"
tar czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_PATH"
echo "  Compressed: ${BACKUP_NAME}.tar.gz"

# --- Retention: remove old backups ---
echo "  Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "tenderai_backup_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete
REMAINING=$(find "$BACKUP_DIR" -name "tenderai_backup_*.tar.gz" | wc -l)
echo "  ${REMAINING} backup(s) retained."

echo "=== Backup Complete ==="
