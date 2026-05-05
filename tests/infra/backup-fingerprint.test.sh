#!/usr/bin/env bash
# ============================================================================
# tests/infra/backup-fingerprint.test.sh — Round 3 PR-C
# ============================================================================
# Smoke tests for verify_public_key_fingerprint() in
#   infra/backup-offsite-sync.sh
#   infra/minio-offsite-sync.sh
#
# Closes audit finding A05-P1-004. Function:
#   - WARN-and-continue if expected-fingerprint file is missing
#   - HARD-FAIL (exit 1) if file exists and on-disk pubkey hash mismatches
#   - INFO-and-continue if hashes match
#
# Run: bash tests/infra/backup-fingerprint.test.sh
# Exit: 0 on all-pass, 1 on first failure.
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")/../.."

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$*"; }

# 1) Function defined in both scripts.
for script in infra/backup-offsite-sync.sh infra/minio-offsite-sync.sh; do
  if ! grep -qE '^verify_public_key_fingerprint\(\)' "$script"; then
    fail "$script: verify_public_key_fingerprint() not defined"
  fi
  pass "$script: verify_public_key_fingerprint() defined"
done

# 2) Both scripts CALL the function (not just define it).
for script in infra/backup-offsite-sync.sh infra/minio-offsite-sync.sh; do
  CALLS=$(grep -nE 'verify_public_key_fingerprint' "$script" \
          | grep -vE '^\s*[0-9]+:verify_public_key_fingerprint\(\)' \
          | grep -vE '^\s*[0-9]+:#' \
          | wc -l)
  if [[ "$CALLS" -lt 1 ]]; then
    fail "$script: verify_public_key_fingerprint() defined but never called"
  fi
  pass "$script: verify_public_key_fingerprint() called"
done

# 3) Behaviour test — exercise the function in a sandbox.
SANDBOX="$(mktemp -d -t pr-c-fingerprint-XXXXXX)"
trap 'rm -rf "$SANDBOX"' EXIT

PUBKEY="$SANDBOX/offsite-backup-public.age"
echo "age1ph2g4v82uxvkhc4ad3qcre5tya6q9htlmvwznm4tt9q5wknvjvcqvfzmek" > "$PUBKEY"
EXPECTED_HASH="$(sha256sum "$PUBKEY" | awk '{print $1}')"

HARNESS="$SANDBOX/harness.sh"
cat > "$HARNESS" <<HARNESS_END
#!/usr/bin/env bash
set -uo pipefail
PUBLIC_KEY="$PUBKEY"
EXPECTED_FINGERPRINT_FILE="\${1:-/dev/null}"
log() { echo "[harness] \$@"; }

$(awk '/^verify_public_key_fingerprint\(\)/,/^}/' infra/backup-offsite-sync.sh)

verify_public_key_fingerprint
HARNESS_END
chmod +x "$HARNESS"

# 3a) Missing fingerprint file -> exit 0 + WARN.
set +e
OUT="$("$HARNESS" "$SANDBOX/does-not-exist" 2>&1)"
RC=$?
set -e
if echo "$OUT" | grep -qE "fingerprint check SKIPPED" && [[ $RC -eq 0 ]]; then
  pass "missing fingerprint file -> warn-and-continue (rc=0)"
else
  fail "missing fingerprint file: rc=$RC out=$OUT"
fi

# 3b) Matching fingerprint -> exit 0 + INFO.
EXPECTED_FILE="$SANDBOX/expected.sha256"
echo "$EXPECTED_HASH" > "$EXPECTED_FILE"
set +e
OUT="$("$HARNESS" "$EXPECTED_FILE" 2>&1)"
RC=$?
set -e
if echo "$OUT" | grep -qE "public key fingerprint verified" && [[ $RC -eq 0 ]]; then
  pass "matching fingerprint -> verified (rc=0)"
else
  fail "matching fingerprint: rc=$RC out=$OUT"
fi

# 3c) Mismatched fingerprint -> exit 1 + ERROR.
echo "0000000000000000000000000000000000000000000000000000000000000000" > "$EXPECTED_FILE"
set +e
OUT="$("$HARNESS" "$EXPECTED_FILE" 2>&1)"
RC=$?
set -e
if echo "$OUT" | grep -qE "public key fingerprint MISMATCH" && [[ $RC -eq 1 ]]; then
  pass "mismatched fingerprint -> MISMATCH error + exit 1"
else
  fail "mismatched fingerprint: rc=$RC out=$OUT"
fi

# 3d) Mismatch error message contains recovery instructions.
if echo "$OUT" | grep -qE "To recover"; then
  pass "mismatch error includes recovery instructions"
else
  fail "mismatch error missing recovery section: $OUT"
fi

echo
echo "All backup-fingerprint assertions passed."
