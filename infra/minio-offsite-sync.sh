#!/usr/bin/env bash
# ============================================================================
# minio-offsite-sync.sh — encrypted offsite mirror for MinIO buckets
#
# Closes the Phase 6.2 MinIO gap. Companion to backup-offsite-sync.sh which
# handles Postgres. Same age + B2 + retention shape; same key custody
# model — the public key lives at /etc/meddoc/offsite-backup-public.age,
# the private key never touches the VPS.
#
# What this backs up:
#   - transcribe-md-audio bucket (TRANSCRIBE_MD_MINIO_BUCKET) — original
#     uploaded audio + dictation + generated PDFs/DOCX. PHI throughout.
#
# What this does NOT back up:
#   - Redis (ephemeral session state, BullMQ queue state — both regenerable
#     from the next worker run).
#   - meddoc-pro tables — postgres-backup grabs the whole pg cluster, so
#     they ride along on the Postgres path. Not touched here.
#
# Run model:
#   - Designed for host crontab, not the postgres-backup sidecar (mc is
#     not on the prodrigestivill image and we don't want to bloat it).
#   - Cadence pairs with the Postgres daily backup; document in
#     scripts/phase-6.2/README.md → cron block.
#
# Required env:
#   BACKBLAZE_KEY_ID            — same key as Postgres path
#   BACKBLAZE_APPLICATION_KEY   — same secret
#   BACKBLAZE_BUCKET            — same bucket (objects keyed by prefix)
#   MINIO_ROOT_USER             — for mc alias
#   MINIO_ROOT_PASSWORD         — for mc alias
#   MINIO_BUCKETS               — space-separated (default: 'transcribe-md-audio')
#
# Required tools on PATH:
#   mc      — MinIO client; install: https://min.io/docs/minio/linux/reference/minio-mc.html
#   age     — apt install age
#   b2      — pip install b2
#   tar     — coreutils
#   sha256sum — coreutils
#
# Required files:
#   /etc/meddoc/offsite-backup-public.age — created by backup-offsite-sync.sh
#     on first run. This script REUSES that key, so the same private key
#     unlocks both Postgres and MinIO blobs.
#
# Side effects:
#   - Stages plaintext bucket contents at /var/tmp/meddoc-minio-stage-XXXXXX
#     (cleanup trap fires on exit — success OR failure). The staging window
#     is bounded by mc + tar runtime (seconds-to-minutes); the host disk
#     is LUKS-encrypted at rest per Phase 6.1, so even an interrupted run
#     leaves no plaintext on cold storage.
#   - Tags each B2 upload with sha256 + bucket name + source hostname.
#   - Object keys: meddoc-pro/minio/<YYYY/MM/DD>/<bucket>-<UTC-timestamp>.tar.age
#
# Exit codes:
#   0   — success
#   78  — config error (EX_CONFIG; missing env or CLI tool)
#   1   — runtime failure
# ============================================================================

set -euo pipefail

readonly LOG_FILE="/var/log/meddoc/minio-offsite-backup.log"
readonly LOG_TAIL_LINES=10000
readonly KEY_DIR="/etc/meddoc"
readonly PUBLIC_KEY="${KEY_DIR}/offsite-backup-public.age"
readonly EX_CONFIG=78
readonly DEFAULT_BUCKETS="transcribe-md-audio"

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

log() {
  local ts
  ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  printf '[%s] %s\n' "$ts" "$*" | tee -a "$LOG_FILE" >&2
}

rotate_log() {
  if [[ -f "$LOG_FILE" ]]; then
    local lines
    lines="$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)"
    if [[ "$lines" -gt "$LOG_TAIL_LINES" ]]; then
      tail -n "$LOG_TAIL_LINES" "$LOG_FILE" > "${LOG_FILE}.tmp"
      mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
  fi
}

require_env() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    log "ERROR: required env var ${var_name} is not set"
    log "       Populate via /opt/meddoc-pro/.env. See scripts/phase-6.2/README.md."
    exit "$EX_CONFIG"
  fi
}

require_cli() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "ERROR: required tool '${cmd}' is not on PATH"
    log "       Hint: ${hint}"
    exit "$EX_CONFIG"
  fi
}

require_pubkey() {
  if [[ ! -f "$PUBLIC_KEY" ]]; then
    log "ERROR: ${PUBLIC_KEY} not found"
    log "       The age keypair is created by infra/backup-offsite-sync.sh on its first"
    log "       run. Activate the Postgres path first; this MinIO path reuses the same key."
    exit "$EX_CONFIG"
  fi
}

# ---------------------------------------------------------------------------
# Stage the bucket. Uses `mc` against the MinIO API endpoint exposed on the
# Docker bridge. The alias is set per-run so credential rotations take
# effect on the next cycle without operator action.
#
# `mc cp --recursive` preserves object names + last-modified timestamps;
# we don't need MinIO-level metadata (bucket policy, lifecycle) because
# the bucket is recreated from infrastructure-as-code on restore, and the
# files alone are the recoverable unit.
# ---------------------------------------------------------------------------
stage_bucket() {
  local bucket="$1"
  local stage_dir="$2"

  log "INFO: staging bucket ${bucket} → ${stage_dir}"

  mc alias set quillmd-minio "${MINIO_ENDPOINT:-http://127.0.0.1:9000}" \
    "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" \
    >>"$LOG_FILE" 2>&1 \
    || {
      log "ERROR: 'mc alias set' failed — check MINIO_ENDPOINT / MINIO_ROOT_USER / MINIO_ROOT_PASSWORD"
      exit 1
    }

  mc cp --recursive --quiet \
    "quillmd-minio/${bucket}/" \
    "${stage_dir}/${bucket}/" \
    >>"$LOG_FILE" 2>&1 \
    || {
      log "ERROR: 'mc cp --recursive' failed for bucket ${bucket}"
      exit 1
    }

  local file_count
  file_count="$(find "${stage_dir}/${bucket}" -type f 2>/dev/null | wc -l)"
  log "INFO: staged ${file_count} object(s) from ${bucket}"
}

b2_authorize() {
  log "INFO: authorizing B2 CLI"
  b2 account authorize "$BACKBLAZE_KEY_ID" "$BACKBLAZE_APPLICATION_KEY" \
    >>"$LOG_FILE" 2>&1 \
    || {
      log "ERROR: 'b2 account authorize' failed — check BACKBLAZE_KEY_ID / BACKBLAZE_APPLICATION_KEY"
      exit 1
    }
}

# ---------------------------------------------------------------------------
# Encrypt + upload. tar streams the staged directory through age into a
# temp file (bounded by /var/tmp space — the bucket size cap), then b2
# uploads the encrypted blob with file-info tags.
# ---------------------------------------------------------------------------
upload_encrypted() {
  local bucket="$1"
  local stage_dir="$2"
  local timestamp
  timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"

  local upload_key
  upload_key="meddoc-pro/minio/$(date -u +'%Y/%m/%d')/${bucket}-${timestamp}.tar.age"

  local enc_path
  enc_path="$(mktemp -t minio-offsite-backup.XXXXXX.tar.age)"

  log "INFO: tarring + encrypting ${stage_dir}/${bucket} → ${enc_path}"
  # tar -C cd's into stage_dir, then archives <bucket>/ as the top-level
  # entry. Restore is `tar -xf <enc-decrypted> -C <target>`; the bucket
  # name is preserved as the top-level dir in the archive.
  tar -cf - -C "$stage_dir" "$bucket" \
    | age --encrypt --recipient "$(cat "$PUBLIC_KEY")" --output "$enc_path" \
    || {
      log "ERROR: tar | age pipeline failed"
      rm -f "$enc_path"
      exit 1
    }

  local enc_size
  enc_size="$(stat -c %s "$enc_path")"

  local enc_sha
  enc_sha="$(sha256sum "$enc_path" | awk '{print $1}')"

  local source_host
  source_host="$(hostname -f 2>/dev/null || hostname)"

  log "INFO: encrypted blob is ${enc_size} bytes (sha256=${enc_sha:0:12}...); uploading to b2://${BACKBLAZE_BUCKET}/${upload_key}"

  b2 file upload \
    --info "sha256=${enc_sha}" \
    --info "minio_bucket=${bucket}" \
    --info "encrypted_size=${enc_size}" \
    --info "source_hostname=${source_host}" \
    --info "uploaded_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    "$BACKBLAZE_BUCKET" \
    "$enc_path" \
    "$upload_key" \
    >>"$LOG_FILE" 2>&1 \
    || {
      log "ERROR: b2 file upload failed for ${upload_key}"
      rm -f "$enc_path"
      exit 1
    }

  # Belt-and-braces: confirm the object exists in B2 by reading it back.
  # A successful upload that the bucket immediately rejects (e.g. retention
  # policy mismatch, quota exceeded) would otherwise pass the upload step
  # and silently fail the next restore drill.
  if ! b2 file info "b2://${BACKBLAZE_BUCKET}/${upload_key}" >>"$LOG_FILE" 2>&1; then
    log "ERROR: b2 file info verification failed — upload may have been rejected post-write"
    rm -f "$enc_path"
    exit 1
  fi

  rm -f "$enc_path"
  log "INFO: upload + verification complete: b2://${BACKBLAZE_BUCKET}/${upload_key}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  rotate_log
  log "INFO: minio-offsite-sync.sh starting"

  require_env "BACKBLAZE_KEY_ID"
  require_env "BACKBLAZE_APPLICATION_KEY"
  require_env "BACKBLAZE_BUCKET"
  require_env "MINIO_ROOT_USER"
  require_env "MINIO_ROOT_PASSWORD"

  require_cli "mc"        "install via https://min.io/docs/minio/linux/reference/minio-mc.html"
  require_cli "age"       "apt install age"
  require_cli "b2"        "pip install b2"
  require_cli "sha256sum" "ships in coreutils"
  require_cli "tar"       "ships in coreutils"

  require_pubkey

  local stage_dir
  stage_dir="$(mktemp -d -p /var/tmp meddoc-minio-stage.XXXXXX)"
  # Trap fires on success AND failure — guarantees plaintext stage cleanup.
  trap 'rm -rf "$stage_dir"' EXIT

  local buckets="${MINIO_BUCKETS:-$DEFAULT_BUCKETS}"
  b2_authorize

  for bucket in $buckets; do
    stage_bucket "$bucket" "$stage_dir"
    upload_encrypted "$bucket" "$stage_dir"
    # Free the staging space between buckets so multi-bucket runs don't
    # snowball /var/tmp usage.
    rm -rf "${stage_dir:?}/${bucket}"
  done

  log "INFO: minio-offsite-sync.sh completed successfully"
}

main "$@"
