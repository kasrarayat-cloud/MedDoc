#!/usr/bin/env bash
# ============================================================================
# backup-offsite-sync.sh — encrypted offsite mirror to Backblaze B2
#
# Closes HIPAA finding h16 (geographically-distinct offsite backup copy).
#
# Wired as the postgres-backup sidecar's POST_BACKUP_COMMAND. Runs after
# prodrigestivill/postgres-backup-local has finished writing the local
# pg_dump under /backups/. Picks up the freshest dump, age-encrypts it
# with the host-resident public key, and uploads the encrypted blob to a
# Backblaze B2 bucket (HIPAA-eligible — operator must sign a BAA with B2
# before populating live credentials).
#
# Why a separate script (vs the existing postscript.sh that runs `mc mirror`):
#   - postscript.sh ships unencrypted dumps to S3-compat storage.
#   - This script adds a defence-in-depth layer: even if B2 credentials or
#     the bucket itself are compromised, the dumps stay confidential because
#     decryption requires an offline private key the attacker doesn't have.
#   - Operators may run BOTH (mc mirror + B2 encrypted) or replace one with
#     the other. They are independent.
#
# Required env (script exits 78 / EX_CONFIG if any are missing):
#   BACKBLAZE_KEY_ID            — application key ID from B2 console
#   BACKBLAZE_APPLICATION_KEY   — secret half of the application key
#   BACKBLAZE_BUCKET            — bucket name (e.g. meddoc-offsite-backups-prod)
#
# Required tools on PATH (script fails with hint if missing):
#   age, age-keygen — modern asymmetric file encryption (https://age-encryption.org)
#   b2              — Backblaze B2 official CLI (`pip install b2`)
#   sha256sum       — coreutils
#
# Required filesystem (script creates these on first run if missing):
#   /etc/meddoc/offsite-backup-public.age   — age public key (mode 0444)
#   /etc/meddoc/offsite-backup-private.age  — age private key (mode 0400, root)
#   /var/log/meddoc/offsite-backup.log      — append-only run log
#
# Side effects:
#   - Generates an age keypair on first run if /etc/meddoc/offsite-backup-private.age
#     does not exist. The PRIVATE KEY IS THE ONLY WAY TO RESTORE BACKUPS — see
#     docs/RUNBOOK_OFFSITE_BACKUP.md "Key custody".
#   - Tags each B2 upload with sha256, dump filename, dump size, source hostname.
#   - Retains the most recent 30 days of encrypted blobs in the bucket; older
#     blobs are deleted. Bucket-level lifecycle rules in B2 should match
#     (documented in the runbook).
#
# Exit codes:
#   0   — success (encrypted upload complete)
#   78  — config error (EX_CONFIG; missing env or missing CLI tool)
#   1   — runtime failure (no dump found, age failed, b2 upload failed)
# ============================================================================

set -euo pipefail

readonly LOG_FILE="/var/log/meddoc/offsite-backup.log"
readonly LOG_TAIL_LINES=10000
readonly KEY_DIR="/etc/meddoc"
readonly PUBLIC_KEY="${KEY_DIR}/offsite-backup-public.age"
readonly PRIVATE_KEY="${KEY_DIR}/offsite-backup-private.age"
readonly LOCAL_BACKUP_DIR="/backups"
readonly RETENTION_DAYS=30
readonly EX_CONFIG=78

# ---------------------------------------------------------------------------
# Logging — write to LOG_FILE and stderr. Rotate (tail) the log on each run
# so a long-running deploy doesn't grow it without bound.
# ---------------------------------------------------------------------------
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

log() {
  local ts
  ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  printf '[%s] %s\n' "$ts" "$*" | tee -a "$LOG_FILE" >&2
}

rotate_log() {
  # Keep only the last LOG_TAIL_LINES lines so the file never grows past a
  # bounded size. Rotation happens at the start of every run.
  if [[ -f "$LOG_FILE" ]]; then
    local lines
    lines="$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)"
    if [[ "$lines" -gt "$LOG_TAIL_LINES" ]]; then
      tail -n "$LOG_TAIL_LINES" "$LOG_FILE" > "${LOG_FILE}.tmp"
      mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
  fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
require_env() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    log "ERROR: required env var ${var_name} is not set"
    log "       Populate via /opt/meddoc-pro/.env after the BAA with Backblaze is signed."
    log "       See docs/RUNBOOK_OFFSITE_BACKUP.md."
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

# ---------------------------------------------------------------------------
# Locate freshest local dump produced by prodrigestivill/postgres-backup-local
#
# Layout (the upstream image creates these):
#   /backups/last/<db>-<dow>.sql.gz       — newest snapshot per weekday
#   /backups/daily/<db>-<date>.sql.gz     — historical
#   /backups/weekly/<db>-<week>.sql.gz
#   /backups/monthly/<db>-<month>.sql.gz
#
# We pick the newest mtime across /backups/last/ specifically; that's the
# file the daily cron just wrote.
# ---------------------------------------------------------------------------
find_latest_dump() {
  if [[ ! -d "${LOCAL_BACKUP_DIR}/last" ]]; then
    log "ERROR: ${LOCAL_BACKUP_DIR}/last does not exist — postgres-backup hasn't run yet?"
    exit 1
  fi

  local latest
  latest="$(find "${LOCAL_BACKUP_DIR}/last" -maxdepth 1 -type f -name '*.sql.gz' \
    -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | head -n 1 \
    | awk '{print $2}')"

  if [[ -z "$latest" ]]; then
    log "ERROR: no *.sql.gz files in ${LOCAL_BACKUP_DIR}/last/"
    exit 1
  fi

  echo "$latest"
}

# ---------------------------------------------------------------------------
# Phase 6.2 threat model: the private key NEVER touches the VPS. It is
# generated on an offline laptop, multi-located in 1Password + a fireproof
# safe, and only the public key is scp'd onto the host at PUBLIC_KEY. So the
# early-return check below is "public key present" only — that is sufficient
# for encryption, and PRIVATE_KEY missing on the VPS is the *expected* state.
#
# The fall-through (auto-generate) branch is a safety net for the legacy
# h16-era flow where both keys were created on the VPS. In Phase 6.2 it
# should NEVER fire in production. If it does, the operator skipped runbook
# §22 step 3 (scp public key onto VPS before first backup run) — discard
# the VPS-generated keypair and re-deploy the offline keypair before any
# further backup runs, otherwise blobs encrypted to the wrong public key
# are unrecoverable.
# ---------------------------------------------------------------------------
ensure_keypair() {
  if [[ -f "$PUBLIC_KEY" ]]; then
    # Phase 6.2: private key lives offline by design;
    # public key is the only thing we need on the VPS.
    return 0
  fi

  log "WARN: ${PUBLIC_KEY} not found — falling back to local keypair generation."
  log "WARN: This branch should NOT fire in Phase 6.2 production. Expected flow:"
  log "WARN:   1) age-keygen on an offline laptop"
  log "WARN:   2) scp <pub-key> root@vps:/etc/meddoc/offsite-backup-public.age"
  log "WARN: If you see this in prod, discard the generated keypair AND re-deploy"
  log "WARN: the offline keypair before any further backup runs."

  mkdir -p "$KEY_DIR"

  # Generate to a tempfile then move atomically so a crash mid-run doesn't
  # leave a half-written private key on disk.
  local tmp_priv
  tmp_priv="$(mktemp -p "$KEY_DIR" .age-priv.XXXXXX)"
  age-keygen -o "$tmp_priv" 2>/dev/null

  # age-keygen writes the public key to stdout when -o is used; recover it
  # from the private-key file's "public key:" comment line.
  local pubkey
  pubkey="$(grep -E '^# public key:' "$tmp_priv" | sed -E 's/^# public key: //')"

  if [[ -z "$pubkey" ]]; then
    log "ERROR: could not extract public key from generated private key"
    rm -f "$tmp_priv"
    exit 1
  fi

  printf '%s\n' "$pubkey" > "${PUBLIC_KEY}.tmp"
  mv "${PUBLIC_KEY}.tmp" "$PUBLIC_KEY"
  mv "$tmp_priv" "$PRIVATE_KEY"

  chmod 0444 "$PUBLIC_KEY"
  chmod 0400 "$PRIVATE_KEY"

  log "INFO: keypair generated; public=${PUBLIC_KEY} private=${PRIVATE_KEY}"
}

# ---------------------------------------------------------------------------
# Round 3 PR-C (audit A05-P1-004): verify the public key on disk matches
# the operator-deployed expected fingerprint. The expected sha256 lives at
# /etc/meddoc/expected-public-key-fingerprint.sha256 — written once by the
# operator immediately after scp'ing the canonical public key onto the VPS.
#
# Failure mode taxonomy:
#   - Mismatch: hard-fail (exit 1). Encrypting with a key whose private half
#               is not in operator custody would produce unrecoverable blobs.
#   - File missing: warn-and-continue (transition mode). PR-C bootstrap
#               instructs the operator to deploy the fingerprint file
#               alongside the public key; until that lands, runs continue
#               with a loud reminder rather than blocking the backup chain.
#
# Override for tests: EXPECTED_FINGERPRINT_FILE env var.
# ---------------------------------------------------------------------------
verify_public_key_fingerprint() {
  local expected_file="${EXPECTED_FINGERPRINT_FILE:-/etc/meddoc/expected-public-key-fingerprint.sha256}"
  if [[ ! -f "$expected_file" ]]; then
    log "WARN: ${expected_file} not present — fingerprint check SKIPPED."
    log "WARN: Round 3 PR-C requires this file. Operator must run, ONCE,"
    log "WARN: after deploying the canonical public key:"
    log "WARN:   sha256sum ${PUBLIC_KEY} | awk '{print \$1}' > ${expected_file}"
    log "WARN:   chmod 644 ${expected_file}"
    log "WARN: Continuing without fingerprint check (transition mode)."
    return 0
  fi

  local actual expected
  actual="$(sha256sum "$PUBLIC_KEY" | awk '{print $1}')"
  expected="$(tr -d '[:space:]' < "$expected_file")"

  if [[ "$actual" != "$expected" ]]; then
    log "ERROR: public key fingerprint MISMATCH — refusing to encrypt."
    log "ERROR:   path:     ${PUBLIC_KEY}"
    log "ERROR:   actual:   ${actual}"
    log "ERROR:   expected: ${expected} (from ${expected_file})"
    log "ERROR:"
    log "ERROR: The public key on disk does not match the canonical key. Possible causes:"
    log "ERROR:   1. The auto-generate fall-through in ensure_keypair() fired (look for"
    log "ERROR:      a 'keypair generated' line in earlier log entries) — encrypt with"
    log "ERROR:      this key and the blob is UNRECOVERABLE because the operator's"
    log "ERROR:      offline private key cannot decrypt it."
    log "ERROR:   2. An attacker swapped the public key to capture future backups."
    log "ERROR:   3. The operator rotated the key and forgot to update ${expected_file}."
    log "ERROR:"
    log "ERROR: To recover (only after verifying which case applies):"
    log "ERROR:   - Case 1: discard the auto-generated keypair, re-deploy the canonical"
    log "ERROR:            public key from offline custody."
    log "ERROR:   - Case 2: incident response — see docs/runbooks/edge-security.md §8.4"
    log "ERROR:            then re-deploy canonical public key."
    log "ERROR:   - Case 3: update the expected fingerprint:"
    log "ERROR:            sha256sum ${PUBLIC_KEY} | awk '{print \$1}' > ${expected_file}"
    exit 1
  fi

  log "INFO: public key fingerprint verified (${actual:0:16}...)"
}

# ---------------------------------------------------------------------------
# B2 authentication. The B2 CLI caches auth in ~/.b2_account_info — we
# re-authenticate on every run so credential rotations take effect on the
# next backup cycle without a manual step.
# ---------------------------------------------------------------------------
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
# Encrypt + upload + tag
# ---------------------------------------------------------------------------
upload_encrypted() {
  local dump_path="$1"
  local dump_name
  dump_name="$(basename "$dump_path")"

  local dump_size
  dump_size="$(stat -c %s "$dump_path")"

  local dump_sha
  dump_sha="$(sha256sum "$dump_path" | awk '{print $1}')"

  local source_host
  source_host="$(hostname -f 2>/dev/null || hostname)"

  local upload_key
  upload_key="meddoc-pro/$(date -u +'%Y/%m/%d')/${dump_name}.age"

  local enc_path
  enc_path="$(mktemp -t offsite-backup.XXXXXX.age)"

  log "INFO: encrypting ${dump_path} (${dump_size} bytes, sha256=${dump_sha:0:12}...)"
  age --encrypt --recipient "$(cat "$PUBLIC_KEY")" --output "$enc_path" "$dump_path" \
    || {
      log "ERROR: age encryption failed"
      rm -f "$enc_path"
      exit 1
    }

  local enc_size
  enc_size="$(stat -c %s "$enc_path")"
  log "INFO: encrypted blob is ${enc_size} bytes; uploading to b2://${BACKBLAZE_BUCKET}/${upload_key}"

  # `b2 file upload` (v4 syntax) takes file-info pairs via --info name=value.
  # Tags are visible in the B2 console + queryable via `b2 file info`.
  b2 file upload \
    --info "sha256=${dump_sha}" \
    --info "dump_filename=${dump_name}" \
    --info "dump_size=${dump_size}" \
    --info "source_hostname=${source_host}" \
    --info "uploaded_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    "$BACKBLAZE_BUCKET" \
    "$enc_path" \
    "$upload_key" \
    >>"$LOG_FILE" 2>&1 \
    || {
      log "ERROR: b2 file upload failed"
      rm -f "$enc_path"
      exit 1
    }

  rm -f "$enc_path"
  log "INFO: upload complete: b2://${BACKBLAZE_BUCKET}/${upload_key}"
}

# ---------------------------------------------------------------------------
# Retention. We delete blobs older than RETENTION_DAYS days. Bucket lifecycle
# rules in B2 should ALSO be configured (documented in runbook §A) — this
# script is a belt-and-braces local cleanup.
#
# `b2 ls --recursive --json` emits one JSON object per file; we parse with
# python (already on the postgres-backup image when the b2 CLI is installed)
# rather than jq to keep the dependency surface small.
# ---------------------------------------------------------------------------
prune_old_blobs() {
  log "INFO: pruning blobs older than ${RETENTION_DAYS} days from b2://${BACKBLAZE_BUCKET}/meddoc-pro/"

  local cutoff_epoch
  cutoff_epoch="$(date -u -d "${RETENTION_DAYS} days ago" +%s)"

  # b2 v4: `b2 ls --recursive --json --with-wildcard <bucket> 'prefix/*'`
  # emits a JSON array of objects with uploadTimestamp (milliseconds since epoch).
  local listing
  listing="$(b2 ls --recursive --json "$BACKBLAZE_BUCKET" "meddoc-pro/" 2>>"$LOG_FILE" || echo '[]')"

  python3 - "$listing" "$cutoff_epoch" <<'PY' >>"$LOG_FILE" 2>&1 || {
import json, subprocess, sys, os
listing_json = sys.argv[1]
cutoff = int(sys.argv[2])
bucket = os.environ["BACKBLAZE_BUCKET"]
try:
    items = json.loads(listing_json)
except json.JSONDecodeError:
    print(f"[prune] listing was not JSON; skipping prune", file=sys.stderr)
    sys.exit(0)
deleted = 0
for it in items:
    uploaded_ms = it.get("uploadTimestamp", 0)
    if uploaded_ms // 1000 < cutoff:
        file_name = it.get("fileName")
        file_id = it.get("fileId")
        if file_name and file_id:
            subprocess.run(
                ["b2", "file", "delete", f"b2id://{file_id}"],
                check=False,
            )
            deleted += 1
print(f"[prune] deleted {deleted} blob(s) older than cutoff", file=sys.stderr)
PY
    log "WARN: prune step exited non-zero (continuing — local upload already succeeded)"
  }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  rotate_log
  log "INFO: backup-offsite-sync.sh starting"

  require_env "BACKBLAZE_KEY_ID"
  require_env "BACKBLAZE_APPLICATION_KEY"
  require_env "BACKBLAZE_BUCKET"

  require_cli "age"        "install via apt: 'apt install age' (or build from https://github.com/FiloSottile/age)"
  require_cli "age-keygen" "ships with age package"
  require_cli "b2"         "install via pip: 'pip install b2'"
  require_cli "sha256sum"  "ships in coreutils (already present on every supported distro)"
  require_cli "python3"    "ships in default distro packages; required for retention pruning"

  ensure_keypair

  # Round 3 PR-C — A05-P1-004 fingerprint check. After ensure_keypair
  # confirms PUBLIC_KEY exists, verify it hashes to the operator-deployed
  # expected fingerprint. Catches: clobbered key, swapped key, and the
  # auto-regenerate fall-through above (which produces a public key the
  # operator doesn't have the private half of). Fails closed on mismatch;
  # warns-and-continues on missing-fingerprint-file (transition mode).
  verify_public_key_fingerprint

  # Phase 6.2: optional positional arg lets a host-side cron pass the dump
  # path explicitly — the host backup dir doesn't match the in-container
  # /backups path the auto-discovery uses. Falls back to find_latest_dump
  # when invoked from inside the postgres-backup sidecar (no arg).
  local dump_path
  dump_path="${1:-$(find_latest_dump)}"
  log "INFO: latest dump: ${dump_path}"

  b2_authorize
  upload_encrypted "$dump_path"
  prune_old_blobs

  log "INFO: backup-offsite-sync.sh completed successfully"
}

main "$@"
