#!/usr/bin/env bash
# ============================================================================
# tests/infra/backup-offsite-sync.test.sh — smoke tests for Phase 6.2
# pre-activation fix in infra/backup-offsite-sync.sh.
#
# Focus: ensure_keypair() public-key-only early return — the security fix
# that closes the silent-backup-poisoning hole. Old check (PRIVATE_KEY &&
# PUBLIC_KEY) would fall through to age-keygen on Phase 6.2 deployments
# where private key lives offline by design, overwriting the operator's
# offline-generated public key.
#
# Run: bash tests/infra/backup-offsite-sync.test.sh
# Exit: 0 on all-pass, 1 on first failure.
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")/../.."
SCRIPT="infra/backup-offsite-sync.sh"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$*"; }

# 1) bash -n parses cleanly
bash -n "$SCRIPT" || fail "bash -n syntax check failed for $SCRIPT"
pass "bash -n syntax check"

# 2) New PUBLIC_KEY-only early return is present
if ! awk '/^ensure_keypair\(\)/,/^}/' "$SCRIPT" \
   | grep -qE 'if \[\[ -f "\$PUBLIC_KEY" \]\]'; then
  fail "ensure_keypair() does not have new PUBLIC_KEY-only early-return check"
fi
pass "ensure_keypair() PUBLIC_KEY-only early return is in place"

# 3) Regression guard — old PRIVATE && PUBLIC check is gone
if awk '/^ensure_keypair\(\)/,/^}/' "$SCRIPT" \
   | grep -qE 'if \[\[ -f "\$PRIVATE_KEY" && -f "\$PUBLIC_KEY" \]\]'; then
  fail "ensure_keypair() still has old PRIVATE && PUBLIC check (Phase 6.2 regression)"
fi
pass "ensure_keypair() old PRIVATE && PUBLIC check is removed"

# 4) Functional — extract ensure_keypair, run with stub public key, verify
#    it returns 0 without invoking age-keygen.
TEST_DIR="$(mktemp -d -t pg62-test.XXXXXX)"
trap 'rm -rf "$TEST_DIR"' EXIT

# Stub public key (no real cryptographic content needed for this test).
echo "age1stub-public-key-for-test-only" > "$TEST_DIR/offsite-backup-public.age"

# Mock age-keygen: fail loudly if invoked. If ensure_keypair fell through
# to the auto-generate branch, age-keygen would run and we'd see exit 99.
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/age-keygen" <<'KEYGEN'
#!/bin/sh
echo "FAIL: age-keygen invoked despite public key present — early-return broke" >&2
exit 99
KEYGEN
chmod +x "$TEST_DIR/bin/age-keygen"

# Sub-shell: source ensure_keypair out of the script with overridden vars.
# The original script declares KEY_DIR / PUBLIC_KEY / PRIVATE_KEY as readonly
# at the top, but the sub-shell never declares them readonly when we set
# them as plain locals here, so the function uses our overrides.
output="$(
  PATH="$TEST_DIR/bin:$PATH" \
  bash -c "
    set -euo pipefail
    PUBLIC_KEY='$TEST_DIR/offsite-backup-public.age'
    PRIVATE_KEY='$TEST_DIR/offsite-backup-private.age'
    KEY_DIR='$TEST_DIR'
    log() { printf '[test-log] %s\\n' \"\$*\" >&2; }
    $(awk '/^ensure_keypair\(\)/,/^}/' "$SCRIPT")
    ensure_keypair && echo 'EARLY_RETURN_OK'
  " 2>&1
)" || fail "ensure_keypair sub-shell errored: $output"

if echo "$output" | grep -q 'EARLY_RETURN_OK'; then
  pass "ensure_keypair() functional: returned without invoking age-keygen"
else
  fail "ensure_keypair() did not early-return cleanly. Sub-shell output: $output"
fi

echo
echo "All tests passed for $SCRIPT (Phase 6.2 ensure_keypair fix)."
