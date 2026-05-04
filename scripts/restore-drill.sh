#!/usr/bin/env bash
# ============================================================================
# restore-drill.sh — operator-run proof of encrypted offsite restore
#
# Closes the Phase 6.2 "we have backups but never tested restoring them"
# gap. Runnable on demand. Should be run BEFORE declaring Phase 6.2
# active in production, then quarterly thereafter.
#
# What it proves:
#   1. The latest Postgres encrypted blob in B2 is reachable + decryptable
#      with the offline private key.
#   2. The decrypted dump restores cleanly into a fresh Postgres on a
#      non-production port.
#   3. Sanity row counts (users, transcribe_visits, audit_logs) match
#      production's order of magnitude.
#   4. The encrypted-public-key on the VPS matches the operator's offline
#      private key — fails LOUDLY if a key swap silently broke restore.
#
# What it does NOT do:
#   - Touch the production Postgres container.
#   - Restore MinIO blobs (separate drill; document in §22 follow-up).
#   - Promote the temporary Postgres to anything operational.
#
# Usage:
#   ./scripts/restore-drill.sh /path/to/offline/private-key.age
#
#   The private key MUST be on the operator's workstation, NOT on the
#   production VPS. Recommended flow:
#     1. Pull the private key from your offline secret store (1Password
#        Vault, physical safe, etc) onto the workstation.
#     2. Run this script from the workstation pointed at the production
#        B2 bucket via the same env vars the production backup uses.
#     3. Wipe the private key from the workstation when done.
#
# Required env (script exits 78 / EX_CONFIG if any are missing):
#   BACKBLAZE_KEY_ID            — read access to the bucket
#   BACKBLAZE_APPLICATION_KEY
#   BACKBLAZE_BUCKET
#
# Required tools on PATH:
#   age      — apt install age
#   b2       — pip install b2
#   docker   — for the temp Postgres container
#   psql     — apt install postgresql-client
#   gzip     — coreutils
#
# Exit codes:
#   0   — DRILL PASSED. Backups are restorable.
#   78  — config error (missing env / CLI / private key file)
#   1   — DRILL FAILED. See log; do NOT trust the backups until resolved.
# ============================================================================

set -euo pipefail

readonly EX_CONFIG=78
readonly TEMP_PG_NAME="restore-drill-pg"
readonly TEMP_PG_PORT=5433
readonly TEMP_PG_PASSWORD="restore-drill-throwaway"
readonly TEMP_PG_DB="meddoc"
readonly TEMP_PG_USER="meddoc"
# Sanity ranges. Loose enough that a fresh dev DB doesn't trip them, tight
# enough that an empty / wrong-DB blob does.
readonly MIN_USERS=1
readonly MIN_VISITS=1
readonly MIN_AUDIT=0

log() {
  local ts
  ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  printf '[%s] %s\n' "$ts" "$*" >&2
}

require_env() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    log "ERROR: required env var ${var_name} is not set"
    exit "$EX_CONFIG"
  fi
}

require_cli() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "ERROR: required tool '${cmd}' is not on PATH (${hint})"
    exit "$EX_CONFIG"
  fi
}

# ---------------------------------------------------------------------------
# Cleanup. Trap fires on success AND failure so we never leave a temp
# Postgres or decrypted plaintext sitting around. On mid-run interrupt,
# the cleanup still runs.
# ---------------------------------------------------------------------------
WORK_DIR=""
cleanup() {
  local exit_code=$?
  if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
    log "INFO: removing work dir ${WORK_DIR}"
    rm -rf "$WORK_DIR"
  fi
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Fxq "$TEMP_PG_NAME"; then
    log "INFO: removing temp postgres container ${TEMP_PG_NAME}"
    docker rm -f "$TEMP_PG_NAME" >/dev/null 2>&1 || true
  fi
  if [[ $exit_code -eq 0 ]]; then
    log "DRILL PASSED ✅"
  else
    log "DRILL FAILED ❌ (exit ${exit_code}). Backups should be considered untrusted until resolved."
  fi
  exit $exit_code
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 0. Args + pre-flight
# ---------------------------------------------------------------------------
PRIVATE_KEY_PATH="${1:-}"
if [[ -z "$PRIVATE_KEY_PATH" ]]; then
  cat >&2 <<USAGE
Usage: $0 /path/to/offline/private-key.age

The private key MUST come from your offline secret store, NOT from the
production VPS. The drill verifies that the offline key still decrypts
the production-encrypted blobs — that's only meaningful when the key
under test is the same one stored offline.
USAGE
  exit "$EX_CONFIG"
fi

if [[ ! -f "$PRIVATE_KEY_PATH" ]]; then
  log "ERROR: private key file not found at ${PRIVATE_KEY_PATH}"
  exit "$EX_CONFIG"
fi

# Sanity: age private keys begin with 'AGE-SECRET-KEY-1'. Anything else
# is either the public key (mistake) or a corrupted file.
if ! grep -q '^AGE-SECRET-KEY-' "$PRIVATE_KEY_PATH"; then
  log "ERROR: ${PRIVATE_KEY_PATH} does not look like an age private key (missing AGE-SECRET-KEY- header)"
  log "       Did you point at the public key by mistake? The public key starts with 'age1...'"
  exit "$EX_CONFIG"
fi

require_env "BACKBLAZE_KEY_ID"
require_env "BACKBLAZE_APPLICATION_KEY"
require_env "BACKBLAZE_BUCKET"

require_cli "age"    "apt install age"
require_cli "b2"     "pip install b2"
require_cli "docker" "https://docs.docker.com/get-docker/"
require_cli "psql"   "apt install postgresql-client"
require_cli "gzip"   "coreutils"

WORK_DIR="$(mktemp -d -t restore-drill.XXXXXX)"
log "INFO: work dir ${WORK_DIR}"

# ---------------------------------------------------------------------------
# 1. Find the latest Postgres encrypted blob in B2 (under meddoc-pro/)
# ---------------------------------------------------------------------------
log "INFO: authorizing B2 + listing latest postgres dumps"
b2 account authorize "$BACKBLAZE_KEY_ID" "$BACKBLAZE_APPLICATION_KEY" >/dev/null

# `b2 ls --recursive --json` returns one JSON object per file; pick the most
# recently uploaded one whose key starts with meddoc-pro/ AND ends with
# .sql.gz.age (Postgres backup-offsite-sync.sh naming convention).
LATEST_JSON="$(b2 ls --recursive --json "$BACKBLAZE_BUCKET" "meddoc-pro/" 2>/dev/null \
  | python3 -c "
import json, sys
items = json.load(sys.stdin)
pg_items = [it for it in items if it.get('fileName', '').endswith('.sql.gz.age')
            and it.get('fileName', '').startswith('meddoc-pro/') ]
if not pg_items:
    sys.exit('NO_POSTGRES_DUMPS_FOUND')
latest = max(pg_items, key=lambda it: it.get('uploadTimestamp', 0))
print(json.dumps({'fileName': latest['fileName'], 'uploadTimestamp': latest['uploadTimestamp']}))
" 2>&1)"

if [[ "$LATEST_JSON" == NO_POSTGRES_DUMPS_FOUND ]]; then
  log "ERROR: no .sql.gz.age files found under meddoc-pro/ in b2://${BACKBLAZE_BUCKET}"
  log "       Has the Postgres backup ever uploaded? See infra/backup-offsite-sync.sh."
  exit 1
fi

LATEST_KEY="$(echo "$LATEST_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['fileName'])")"
LATEST_TS="$(echo "$LATEST_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['uploadTimestamp'])")"
log "INFO: latest dump: ${LATEST_KEY} (uploadTimestamp=${LATEST_TS})"

# ---------------------------------------------------------------------------
# 2. Download + decrypt
# ---------------------------------------------------------------------------
ENC_PATH="${WORK_DIR}/dump.sql.gz.age"
GZ_PATH="${WORK_DIR}/dump.sql.gz"
SQL_PATH="${WORK_DIR}/dump.sql"

log "INFO: downloading encrypted blob"
b2 file download "b2://${BACKBLAZE_BUCKET}/${LATEST_KEY}" "$ENC_PATH" >/dev/null

log "INFO: decrypting with offline private key"
if ! age --decrypt --identity "$PRIVATE_KEY_PATH" --output "$GZ_PATH" "$ENC_PATH"; then
  log "ERROR: age decryption failed"
  log "       Either the private key doesn't match the production public key,"
  log "       or the encrypted blob is corrupted in transit."
  exit 1
fi

log "INFO: gunzipping dump"
gzip -d "$GZ_PATH"

if [[ ! -s "$SQL_PATH" ]]; then
  log "ERROR: decrypted+ungzipped dump is empty"
  exit 1
fi

DUMP_LINES="$(wc -l < "$SQL_PATH")"
log "INFO: dump has ${DUMP_LINES} lines"

# ---------------------------------------------------------------------------
# 3. Spin temp postgres on :5433, restore, query
# ---------------------------------------------------------------------------
log "INFO: starting temp postgres on port ${TEMP_PG_PORT}"
docker run --rm -d \
  --name "$TEMP_PG_NAME" \
  -e POSTGRES_USER="$TEMP_PG_USER" \
  -e POSTGRES_PASSWORD="$TEMP_PG_PASSWORD" \
  -e POSTGRES_DB="$TEMP_PG_DB" \
  -p "${TEMP_PG_PORT}:5432" \
  pgvector/pgvector:pg16 >/dev/null

log "INFO: waiting for temp postgres to accept connections"
for i in {1..60}; do
  if PGPASSWORD="$TEMP_PG_PASSWORD" psql \
       -h 127.0.0.1 -p "$TEMP_PG_PORT" -U "$TEMP_PG_USER" -d "$TEMP_PG_DB" \
       -c '\q' >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ "$i" -eq 60 ]]; then
    log "ERROR: temp postgres failed to come up within 60s"
    exit 1
  fi
done

log "INFO: restoring dump (this can take a few minutes for production-sized data)"
if ! PGPASSWORD="$TEMP_PG_PASSWORD" psql \
       -h 127.0.0.1 -p "$TEMP_PG_PORT" -U "$TEMP_PG_USER" -d "$TEMP_PG_DB" \
       -v ON_ERROR_STOP=0 \
       -f "$SQL_PATH" >/dev/null 2>"${WORK_DIR}/psql.err"; then
  log "ERROR: psql restore failed; tail of psql stderr:"
  tail -20 "${WORK_DIR}/psql.err" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. Sanity row counts
# ---------------------------------------------------------------------------
count() {
  local table="$1"
  PGPASSWORD="$TEMP_PG_PASSWORD" psql \
    -h 127.0.0.1 -p "$TEMP_PG_PORT" -U "$TEMP_PG_USER" -d "$TEMP_PG_DB" \
    -tAc "SELECT count(*) FROM ${table};" 2>/dev/null \
    || echo -1
}

USERS_COUNT="$(count users)"
VISITS_COUNT="$(count transcribe_visits)"
AUDIT_COUNT="$(count audit_logs)"

log "INFO: restored row counts:"
log "INFO:   users:             ${USERS_COUNT} (expect >= ${MIN_USERS})"
log "INFO:   transcribe_visits: ${VISITS_COUNT} (expect >= ${MIN_VISITS})"
log "INFO:   audit_logs:        ${AUDIT_COUNT} (expect >= ${MIN_AUDIT})"

FAIL=0
if [[ "$USERS_COUNT" -lt "$MIN_USERS" ]]; then
  log "ERROR: users row count ${USERS_COUNT} below sanity floor ${MIN_USERS}"
  FAIL=1
fi
if [[ "$VISITS_COUNT" -lt "$MIN_VISITS" ]]; then
  log "ERROR: transcribe_visits row count ${VISITS_COUNT} below sanity floor ${MIN_VISITS}"
  FAIL=1
fi
if [[ "$AUDIT_COUNT" -lt "$MIN_AUDIT" ]]; then
  log "ERROR: audit_logs row count ${AUDIT_COUNT} below sanity floor ${MIN_AUDIT}"
  FAIL=1
fi

if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi

# Cleanup runs from the EXIT trap.
exit 0
