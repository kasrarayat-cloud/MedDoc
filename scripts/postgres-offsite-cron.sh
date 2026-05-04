#!/usr/bin/env bash
# ============================================================================
# postgres-offsite-cron.sh — host crontab wrapper for Postgres offsite backup
#
# Closes Phase 6.2 Concern #1: infra/backup-offsite-sync.sh is mounted into
# the postgres-backup sidecar at /scripts/backup-offsite-sync.sh:ro, but the
# sidecar's POST_BACKUP_COMMAND still points at the older h16 mc-mirror-to-
# S3 path (postscript.sh). Rather than swap the sidecar wiring (compose.yml
# change, restart required), Phase 6.2 runs the encrypted-B2 chain from the
# host as a parallel cron — sidecar's existing flow stays untouched, the
# encrypted offsite leg runs alongside it.
#
# Symmetrical to scripts/minio-offsite-cron.sh: same logging shape, same
# Slack alert hook, same 30-day log retention.
#
# Wiring (host crontab, root):
#   0 4 * * *  /opt/meddoc-pro/scripts/postgres-offsite-cron.sh
#
# Cadence: 04:00 UTC, ~one hour after MinIO's offsite cron at 03:00 UTC and
# downstream of the sidecar's @daily rotation (which lands fresh dumps in
# /opt/meddoc-pro/backups/last/ shortly after 00:00 UTC). Spacing keeps
# Postgres + MinIO uploads from colliding on the host's upstream link.
#
# Required env (sourced from /opt/meddoc-pro/.env):
#   BACKBLAZE_KEY_ID, BACKBLAZE_APPLICATION_KEY, BACKBLAZE_BUCKET
# Optional:
#   QUILLMD_BACKUP_ALERT_WEBHOOK — Slack-incoming-webhook URL; on failure,
#                                   posts a one-line "Postgres offsite backup
#                                   FAILED" message. No-op if unset.
#
# Logs:
#   /var/log/quillmd-backups/postgres-<UTC-date>.log — one file per run
#   Self-rotating: files older than 30 days are deleted at the start of
#   each run (so a stalled host doesn't grow the log dir without bound).
#
# 24h grace period:
#   If no fresh dump is found in /opt/meddoc-pro/backups/last/ (e.g. cron
#   activated before the sidecar has completed its first @daily run),
#   exit 0 cleanly with a log line and NO Slack alert. Once the first
#   dump lands, all subsequent runs find one. This avoids spurious "FAIL"
#   pages during the activation window.
#
# Exit codes — propagated from infra/backup-offsite-sync.sh when invoked:
#   0   — success (or no dump yet, see grace period)
#   78  — config error (missing env / CLI tool)
#   1   — runtime failure
# ============================================================================

set -uo pipefail

readonly LOG_DIR="/var/log/quillmd-backups"
readonly LOG_RETENTION_DAYS=30
readonly REPO_ROOT="/opt/meddoc-pro"
readonly SYNC_SCRIPT="${REPO_ROOT}/infra/backup-offsite-sync.sh"
readonly ENV_FILE="${REPO_ROOT}/.env"
readonly HOST_BACKUP_DIR="${REPO_ROOT}/backups"

mkdir -p "$LOG_DIR"

# Rotate: drop logs older than 30 days. Find on a missing dir would error
# under set -e, but we just mkdir'd it.
find "$LOG_DIR" -maxdepth 1 -type f -name 'postgres-*.log' -mtime +"$LOG_RETENTION_DAYS" \
  -delete 2>/dev/null || true

# One log file per run (UTC date in name; multiple runs in one day append).
LOG_FILE="${LOG_DIR}/postgres-$(date -u +'%Y-%m-%d').log"

post_alert() {
  # Slack incoming-webhook is the only supported alert sink today. Email
  # could be added by piping into `mail` if the host has an MTA configured.
  # Both are no-op when the relevant env var is unset — the cron is fire-
  # and-forget by design.
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
  printf '\n========== postgres-offsite-cron.sh @ %s ==========\n' "$start_ts"
} >> "$LOG_FILE"

if [[ ! -x "$SYNC_SCRIPT" ]]; then
  printf 'ERROR: %s missing or not executable\n' "$SYNC_SCRIPT" >> "$LOG_FILE"
  post_alert "QuillMD Postgres offsite backup FAILED at ${start_ts}: sync script ${SYNC_SCRIPT} missing or not executable."
  exit 1
fi

# 24h grace period — check the host backup dir first. If the sidecar hasn't
# yet written a dump, exit 0 cleanly without alerting (avoids spurious pages
# during the activation window before the first @daily run completes).
if [[ ! -d "${HOST_BACKUP_DIR}/last" ]]; then
  printf 'INFO: %s/last not present — sidecar has not run yet; exiting cleanly (24h grace).\n' \
    "$HOST_BACKUP_DIR" >> "$LOG_FILE"
  exit 0
fi

DUMP_PATH="$(find "${HOST_BACKUP_DIR}/last" -maxdepth 1 -type f -name '*.sql.gz' \
  -printf '%T@ %p\n' 2>/dev/null \
  | sort -nr \
  | head -n 1 \
  | awk '{print $2}')"

if [[ -z "$DUMP_PATH" ]]; then
  printf 'INFO: no *.sql.gz dumps in %s/last — sidecar may not have completed today; exiting cleanly (24h grace).\n' \
    "$HOST_BACKUP_DIR" >> "$LOG_FILE"
  exit 0
fi

printf 'INFO: invoking sync script with dump %s\n' "$DUMP_PATH" >> "$LOG_FILE"

# Pass the host-discovered dump path explicitly — the sync script's auto-
# discovery (find_latest_dump) targets the in-container /backups path, which
# does not exist on the host. The optional positional arg added in the same
# Phase 6.2 PR makes this work without modifying compose.yml mounts.
"$SYNC_SCRIPT" "$DUMP_PATH" >> "$LOG_FILE" 2>&1
rc=$?

if [[ "$rc" -ne 0 ]]; then
  tail_log="$(tail -20 "$LOG_FILE" 2>/dev/null || echo 'no log content')"
  post_alert "QuillMD Postgres offsite backup FAILED at ${start_ts} (exit ${rc}). Tail: ${tail_log}"
fi

exit "$rc"
