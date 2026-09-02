#!/usr/bin/env bash
# ============================================================================
# REAP SESSION SCRATCH — shred files, refusing anything outside the sandbox.
#   0 = every target shredded   1 = one or more REFUSED or failed
# ----------------------------------------------------------------------------
# ⚠️ WHY THIS EXISTS RATHER THAN A `shred` GRANT. Ruling #166 granted `shred`
# and the grant was written twice, wrongly, both times:
#
#   Bash(shred:*)                              — no scope at all
#   Bash(shred -u -n 3 -z:*)                   — scopes the FLAGS
#   Bash(shred -u -n 3 -z /tmp/claude-1000/:*) — scopes the TEXT, not the PATH
#
# The third looks right and is not. A permission entry is a COMMAND-TEXT PREFIX,
# so it admits everything that merely starts with those characters:
#
#   shred -u -n 3 -z /tmp/claude-1000/../../opt/meddoc-pro/.env
#       -> prefix matches, and normalises to /opt/meddoc-pro/.env, which the
#          same settings file DENIES READING
#   shred -u -n 3 -z /tmp/claude-1000/x /opt/meddoc-pro/.env
#       -> `shred` takes FILE..., so the second operand goes anywhere
#
# ⚠️ NO PREFIX PATTERN CAN FIX THAT, because the hole is in what comes AFTER the
# prefix and the matcher does not parse paths. The repository's dominant
# convention — 35 entries of `Bash(bash scripts/<named>.sh:*)` — does not have
# this weakness: nothing after the prefix can change WHICH FILE RUNS. So the
# scope moves into a script that can actually resolve a path and refuse.
#
# ⚠️ AND IT IS FAIL-CLOSED ON CANNOT-TELL. An unresolvable path, a symlink
# pointing out of the sandbox, or a missing `shred` all REFUSE.
# ============================================================================
set -uo pipefail

SANDBOX="/tmp/claude-1000/"

command -v shred >/dev/null 2>&1 || {
  echo "🔴 reap: no shred on PATH. Refusing — a reap that cannot shred must not"
  echo "   fall back to rm: unlinking turns a recoverable failure into a"
  echo "   permanent one, because the file is gone and its blocks remain."
  exit 1
}

[ "$#" -gt 0 ] || { echo "usage: reap-session-scratch.sh <file>..."; exit 1; }

rc=0
for target in "$@"; do
  # Resolve symlinks and `..` BEFORE deciding. `realpath -m` resolves a path
  # that may not exist, which is what makes the check honest about traversal.
  resolved="$(realpath -m -- "$target" 2>/dev/null || true)"
  if [ -z "$resolved" ]; then
    echo "🔴 REFUSED (unresolvable): $target"; rc=1; continue
  fi
  case "$resolved" in
    "$SANDBOX"*) : ;;
    *) echo "🔴 REFUSED (outside $SANDBOX): $target -> $resolved"; rc=1; continue ;;
  esac
  if [ ! -e "$resolved" ]; then
    echo "   skipped (absent): $resolved"; continue
  fi
  if shred -u -n 3 -z -- "$resolved"; then
    echo "   shredded: $resolved"
  else
    # ⚠️ REPORTED, NEVER SWALLOWED. AGENTS.md: check exit codes, escalate the
    # failures, and only then remove a directory.
    echo "🔴 SHRED FAILED (exit $?): $resolved"; rc=1
  fi
done
exit $rc
