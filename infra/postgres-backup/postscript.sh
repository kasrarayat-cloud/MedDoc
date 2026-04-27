#!/usr/bin/env bash
# ============================================================================
# postgres-backup-local POST_BACKUP_COMMAND — push the freshly-rotated
# /backups/last/ snapshots to S3-compatible offsite storage.
#
# Closes h16-offsite-backup. Backups previously lived only on the same VPS
# as postgres — single-failure-domain risk.
#
# Behaviour: if ALL of the REMOTE_BACKUP_S3_* env vars are present, mirror
# /backups/last/ to s3://$REMOTE_BACKUP_S3_BUCKET/. If any required var is
# missing, exit 0 silently — the daily cron still runs the local backup,
# the offsite leg is just a no-op until creds are wired.
#
# This means the script is safe to land BEFORE Hetzner Object Storage
# is provisioned. See docs/H16_OFFSITE_BACKUP_PROCEDURE.md for the
# end-to-end runbook (provision bucket → set env vars → restart sidecar →
# verify).
#
# Required env (all four must be set to enable):
#   REMOTE_BACKUP_S3_ENDPOINT      e.g. https://<region>.your-objectstorage.com
#   REMOTE_BACKUP_S3_BUCKET        e.g. meddoc-backup-prod
#   REMOTE_BACKUP_S3_ACCESS_KEY    bucket access key
#   REMOTE_BACKUP_S3_SECRET_KEY    bucket secret
# Optional:
#   REMOTE_BACKUP_S3_REGION        defaults to "us-east-1" (S3-API-compatible
#                                  endpoints usually accept any region label)
#   REMOTE_BACKUP_PREFIX           key prefix inside the bucket; default ""
# ============================================================================

set -euo pipefail

if [[ -z "${REMOTE_BACKUP_S3_ENDPOINT:-}" \
   || -z "${REMOTE_BACKUP_S3_BUCKET:-}" \
   || -z "${REMOTE_BACKUP_S3_ACCESS_KEY:-}" \
   || -z "${REMOTE_BACKUP_S3_SECRET_KEY:-}" ]]; then
  echo "[postscript] REMOTE_BACKUP_* not set — skipping offsite push." >&2
  exit 0
fi

REGION="${REMOTE_BACKUP_S3_REGION:-us-east-1}"
PREFIX="${REMOTE_BACKUP_PREFIX:-}"
ENDPOINT="${REMOTE_BACKUP_S3_ENDPOINT%/}"
BUCKET="$REMOTE_BACKUP_S3_BUCKET"

# Download mc once + cache in /backups/.mc-bin (the bind-mounted host
# directory — survives container restarts without rebuilding the image).
MC_BIN="/backups/.mc-bin"
if [[ ! -x "$MC_BIN" ]]; then
  echo "[postscript] downloading mc..." >&2
  curl -fsSL --max-time 60 \
    https://dl.min.io/client/mc/release/linux-amd64/mc \
    -o "$MC_BIN.tmp"
  chmod +x "$MC_BIN.tmp"
  mv "$MC_BIN.tmp" "$MC_BIN"
fi

# mc config dir must be writable; uid 999 owns /backups so use it.
export MC_CONFIG_DIR="/backups/.mc-config"
mkdir -p "$MC_CONFIG_DIR"

"$MC_BIN" alias set --quiet remote \
  "$ENDPOINT" "$REMOTE_BACKUP_S3_ACCESS_KEY" "$REMOTE_BACKUP_S3_SECRET_KEY" \
  --api S3v4 >/dev/null

# Mirror only the gzipped dumps — never the .mc-* caches we created.
"$MC_BIN" mirror --quiet --overwrite \
  --exclude ".mc-*" \
  /backups/last/ \
  "remote/${BUCKET}/${PREFIX}last/" \
  >/dev/null

echo "[postscript] offsite mirror complete: ${ENDPOINT}/${BUCKET}/${PREFIX}last/" >&2
