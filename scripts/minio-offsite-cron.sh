#!/usr/bin/env bash
# ============================================================================
# minio-offsite-cron.sh — host crontab wrapper for MinIO offsite backup
#
# Closes the Phase 6.2 cron-wiring gap for the MinIO path. Postgres has
# its own cron via the postgres-backup container's built-in scheduler;
# MinIO needs a host-side wrapper because the underlying script
# (infra/minio-offsite-sync.sh) is a host tool.
#
# Wiring (host crontab):
#   0 3 * * *  /opt/meddoc-pro/scripts/minio-offsite-cron.sh
#
# Cadence pairs with the Postgres daily 03:00 UTC backup so a single
# day's worth of QuillMD state lands in B2 in one window.
#
# Required env (sourced from /opt/meddoc-pro/.env):
#   BACKBLAZE_KEY_ID, BACKBLAZE_APPLICATION_KEY, BACKBLAZE_BUCKET
#   MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
# Optional:
#   QUILLMD_BACKUP_ALERT_WEBHOOK — Slack-incoming-webhook URL; on failure,
#                                   posts a one-line "MinIO offsite backup
#                                   FAILED" message. No-op if unset.
#
# Logs:
#   /var/log/quillmd-backups/minio-<UTC-date>.log — one file per run
#   Self-rotating: files older than 30 days are deleted at the start of
#   each run (so a stalled host doesn't grow the log dir without bound).
#
# Exit codes — propagated from infra/minio-offsite-sync.sh:
#   0   — success
#   78  — config error
#   1   — runtime failure
# ============================================================================

set -uo pipefail

readonly LOG_DIR="/var/log/quillmd-backups"
readonly LOG_RETENTION_DAYS=30
readonly REPO_ROOT="/opt/meddoc-pro"
readonly SYNC_SCRIPT="${REPO_ROOT}/infra/minio-offsite-sync.sh"
readonly ENV_FILE="${REPO_ROOT}/.env"

mkdir -p "$LOG_DIR"

# Rotate: drop logs older than 30 days. Find on a missing dir would error
# under set -e, but we just mkdir'd it.
find "$LOG_DIR" -maxdepth 1 -type f -name 'minio-*.log' -mtime +"$LOG_RETENTION_DAYS" \
  -delete 2>/dev/null || true

# One log file per run (UTC date in name; multiple runs in one day append).
LOG_FILE="${LOG_DIR}/minio-$(date -u +'%Y-%m-%d').log"

post_alert() {
  # Slack incoming-webhook is the only supported alert sink today (cheap +
  # Kasra already has Slack). Email could be added by piping into `mail`
  # if the host has an MTA configured. Both are no-op when the relevant
  # env var is unset — the cron is fire-and-forget by design.
  local message="$1"
  local webhook="${QUILLMD_BACKUP_ALERT_WEBHOOK:-}"
  if [[ -z "$webhook" ]]; then
    return 0
  fi
  # Single shot, short timeout — alert plumbing failures must not gate the
  # cron's exit code. The backup itself succeeded or failed independently;
  # the alert is just a heads-up.
  local payload
  payload="$(printf '%s' "$message" | python3 -c 'import json,sys;print(json.dumps({"text":sys.stdin.read()}))')"
  curl --max-time 8 --silent --show-error \
    -X POST -H 'Content-Type: application/json' \
    --data "$payload" \
    "$webhook" >/dev/null 2>&1 || true
}

# Source env. Allow file to be missing in dev — the sync script will fail
# with EX_CONFIG anyway when it tries to read the required vars.
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

start_ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
{
  printf '\n========== minio-offsite-cron.sh @ %s ==========\n' "$start_ts"
} >> "$LOG_FILE"

if [[ ! -x "$SYNC_SCRIPT" ]]; then
  printf 'ERROR: %s missing or not executable\n' "$SYNC_SCRIPT" >> "$LOG_FILE"
  post_alert "QuillMD MinIO offsite backup FAILED at ${start_ts}: sync script ${SYNC_SCRIPT} missing or not executable."
  exit 1
fi

# Run sync. Capture exit code so we can post the alert ourselves rather
# than rely on EXIT trap + set -e (clearer flow for the cron-failure path).
"$SYNC_SCRIPT" >> "$LOG_FILE" 2>&1
rc=$?

if [[ "$rc" -ne 0 ]]; then
  tail_log="$(tail -20 "$LOG_FILE" 2>/dev/null || echo 'no log content')"
  post_alert "QuillMD MinIO offsite backup FAILED at ${start_ts} (exit ${rc}). Tail: ${tail_log}"
fi

exit "$rc"
