#!/usr/bin/env bash
# ============================================================================
# push-with-cancellation.sh — the DISCIPLINED form of the pre-push override.
# ----------------------------------------------------------------------------
# The pre-push hook refuses a push while runs are in flight on the pushed ref,
# and offers exactly one legitimate release valve:
#
#     DECLARE_CANCELLATION="<reason>" git push …
#
# ⚠️ THE UNATTENDED LOOP CANNOT ISSUE THAT LINE. Its allowlist grants commands
# by NAME, and a compound `VAR=value command` is a SHAPE, not a command —
# granting the shape would grant every VAR=value prefix to every command, which
# is categorically wider than anything else in that file. So the override was
# unreachable for the one actor the hook was written to keep honest. Measured
# cost: ~40 min (batch 1 session 06) and ~41 min (batch 2 session 01), both
# spent waiting for a gate cycle the session was entitled to skip.
#
# ⚠️ THE ARGUMENT FOR EXISTING AT ALL, RECORDED SO IT IS NOT RE-LITIGATED:
# refusing the grant does NOT withhold the capability. The loop already holds
# `gh run cancel` — the same outcome through another door, with no declaration
# and no log line. What refusal withheld was the DISCIPLINE: the reason, in
# somebody's words, in the transcript. A guard that refuses, offers an escape
# hatch, and has that hatch blocked by an unrelated layer teaches sessions the
# undisciplined door. This wrapper restores the record-keeping, which is the
# entire point of the declaration.
#
# Owner-ruled 2026-08-17. House precedent: retire-branch.sh, merge-pr.sh — a
# named wrapper is allowlistable; the raw shape stays denied.
#
#   bash scripts/push-with-cancellation.sh "<reason>" [git push args…]
#
# Exit: 0 push succeeded · 1 refused (bad/absent reason) · 2 cannot tell
# ============================================================================
set -uo pipefail

die1() { printf '🔴 push-with-cancellation: %s\n' "$*" >&2; exit 1; }
die2() { printf '🔴 push-with-cancellation: %s\n' "$*" >&2; exit 2; }

# ⚠️ FAIL-CLOSED ON A MISSING LIB. A wrapper that silently skipped the shared
# validator because a file moved would be worse than no wrapper — it would look
# like discipline and enforce nothing.
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/inflight.sh"
[ -r "$LIB" ] || die2 "cannot tell — $LIB is missing or unreadable."
# shellcheck source=lib/inflight.sh
. "$LIB"

REASON="${1:-}"
[ $# -ge 1 ] || die1 "no reason given.

    bash scripts/push-with-cancellation.sh \"<why this cancellation is deliberate>\" [git push args…]

  This wrapper exists ONLY to carry a declaration. A push with no reason is a
  plain push — use \`git push\`, and let the hook refuse you if runs are live."
shift

# ⚠️ THE EMPTY CASE IS THE WRAPPER'S OWN RULE, AND IT IS NOT IN THE SHARED
# VALIDATOR BY DESIGN. `inflight_declaration_ok ""` returns 0, because the HOOK
# calls it on every push and an empty value there means "no declaration
# offered" — the normal path. Here an empty value means the caller invoked the
# override and declared nothing, which is the one thing this script must refuse.
# Same validator, one extra rule that genuinely belongs to this caller.
[ -n "${REASON//[[:space:]]/}" ] || die1 "the reason is empty or whitespace.
  An audit trail's \"why\" is somebody's words or nothing."

# The token/length rules live in ONE place and are reused, never reimplemented:
# a second copy drifts from the first the day either is fixed.
inflight_declaration_ok "$REASON" || die1 "(declaration refused above)"

# ⚠️ ECHOED TO STDERR BEFORE THE PUSH, BECAUSE STDERR *IS* THE LOG FOR AN
# UNATTENDED SESSION. If the push fails, the declaration is still on the record
# — the decision was made, and a decision that is only logged on success is a
# log that flatters.
{
  echo "═══════════════════════════════════════════════════════════════════"
  echo "DECLARED CANCELLATION — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "  by     : ${USER:-unknown}@$(hostname 2>/dev/null || echo host)"
  echo "  ref    : $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "  reason : $REASON"
  echo "═══════════════════════════════════════════════════════════════════"
} >&2

DECLARE_CANCELLATION="$REASON" git push "$@"
rc=$?
[ $rc -eq 0 ] || die1 "git push exited $rc — the declaration above stands, the push did not."
echo "🟢 push-with-cancellation: pushed under a declared cancellation." >&2
