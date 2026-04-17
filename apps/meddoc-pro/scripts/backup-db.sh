#!/usr/bin/env bash
# ============================================================================
# MedDoc Pro — Postgres backup script
# ----------------------------------------------------------------------------
# Runs pg_dump against the containerized postgres service, writes a
# timestamped .sql.gz to $BACKUP_DIR, keeps the last $RETAIN_COUNT files,
# and (if configured) uploads to S3-compatible object storage.
#
# DESIGN NOTES:
#   - Runs on the HOST (cron) — not inside a container. It shells into the
#     postgres container via `docker compose exec` to dump the DB.
#   - Uses pg_dump's custom format (`-Fc`) which is smaller, restorable via
#     pg_restore with selective object restore, and faster than plain SQL.
#   - Retention is local-file based: $RETAIN_COUNT newest files kept,
#     older ones deleted. S3 side should have its own lifecycle policy.
#   - On failure, exits non-zero so cron mails the operator.
#
# INSTALL:
#   1. chmod +x scripts/backup-db.sh
#   2. mkdir -p /var/backups/meddoc && chown $USER: /var/backups/meddoc
#   3. Add to crontab (run daily at 03:15):
#        15 3 * * * /opt/meddoc-pro/scripts/backup-db.sh >> /var/log/meddoc-backup.log 2>&1
#   4. (Optional) Set S3 vars in /etc/default/meddoc-backup:
#        export S3_BUCKET=meddoc-backups
#        export S3_PREFIX=postgres/
#        export AWS_ACCESS_KEY_ID=...
#        export AWS_SECRET_ACCESS_KEY=...
#        export AWS_DEFAULT_REGION=...
#      Then source it in cron: `. /etc/default/meddoc-backup && /opt/meddoc-pro/scripts/backup-db.sh`
# ============================================================================

set -euo pipefail

# ---- config ----------------------------------------------------------------
COMPOSE_DIR="${COMPOSE_DIR:-/opt/meddoc-pro}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/meddoc}"
RETAIN_COUNT="${RETAIN_COUNT:-14}"    # keep 14 days of local dumps
DB_USER="${DB_USER:-meddoc}"
DB_NAME="${DB_NAME:-meddoc}"
COMPOSE_SERVICE="${COMPOSE_SERVICE:-postgres}"

# Optional S3 upload. If S3_BUCKET is empty, skip upload.
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-}"

# ---- ensure output dir -----------------------------------------------------
mkdir -p "$BACKUP_DIR"

# ---- dump ------------------------------------------------------------------
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="$BACKUP_DIR/meddoc-${TIMESTAMP}.dump"

echo "[$(date -u +%FT%TZ)] Starting backup → $DUMP_FILE"

cd "$COMPOSE_DIR"

# pg_dump in custom format (-Fc). We pipe stdin/stdout through docker
# compose so nothing transient sits inside the container's filesystem.
docker compose exec -T "$COMPOSE_SERVICE" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc \
  > "$DUMP_FILE"

# Sanity check — fail loudly if the dump is suspiciously small
DUMP_SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || stat -f%z "$DUMP_FILE")
if [ "$DUMP_SIZE" -lt 1024 ]; then
  echo "[$(date -u +%FT%TZ)] ERROR: dump is only ${DUMP_SIZE} bytes — aborting" >&2
  rm -f "$DUMP_FILE"
  exit 1
fi

echo "[$(date -u +%FT%TZ)] Dump OK (${DUMP_SIZE} bytes)"

# ---- S3 upload (optional) --------------------------------------------------
if [ -n "$S3_BUCKET" ]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "[$(date -u +%FT%TZ)] WARN: S3_BUCKET set but 'aws' CLI not found — skipping upload" >&2
  else
    S3_KEY="${S3_PREFIX}meddoc-${TIMESTAMP}.dump"
    echo "[$(date -u +%FT%TZ)] Uploading to s3://${S3_BUCKET}/${S3_KEY}"
    aws s3 cp "$DUMP_FILE" "s3://${S3_BUCKET}/${S3_KEY}"
    echo "[$(date -u +%FT%TZ)] Upload OK"
  fi
fi

# ---- retention — keep newest N, delete older -------------------------------
# Sort by mtime descending, skip the first $RETAIN_COUNT, delete the rest.
cd "$BACKUP_DIR"
# shellcheck disable=SC2010  (ls output is fine here — filenames are ASCII)
ls -1t meddoc-*.dump 2>/dev/null | tail -n +$((RETAIN_COUNT + 1)) | while read -r old; do
  echo "[$(date -u +%FT%TZ)] Pruning $old"
  rm -f -- "$old"
done

echo "[$(date -u +%FT%TZ)] Backup complete."
