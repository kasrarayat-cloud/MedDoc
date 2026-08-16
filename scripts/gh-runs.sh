#!/usr/bin/env bash
# ============================================================================
# gh-runs.sh — the ONLY sanctioned door to `gh run list --commit`.
# ----------------------------------------------------------------------------
# ⚠️ IT REFUSES ANY SHA UNDER 40 CHARACTERS, and that refusal is the whole
# product. `gh run list --commit <SHORT-sha>` returns **[]** for ANY
# abbreviation — exit 0, no warning, no "ambiguous". A false all-clear that is
# indistinguishable from a quiet branch.
#
# ⚠️ THIS EXISTS BECAUSE THE RULE WAS ALREADY WRITTEN DOWN AND STILL FIRED
# TWICE ON ITS OWN AUTHOR IN ONE SESSION — once on a deploy gate, where a
# waiter polling the short form read [] as "nothing in flight" and exited while
# three required checks were still running. `scripts/lib/inflight.sh` had
# guarded this correctly since it was written; the hole was that ad-hoc waiters
# call `gh run list` DIRECTLY and never reach the lib.
#
#     A RULE THAT DOES NOT CHANGE WHAT HAPPENS BECOMES MECHANISM.
#
# The lib stays the door for the hook and the merge wrapper. This is the door
# for everything else — waiters, citation checks, one-off polls.
#
# USAGE
#   bash scripts/gh-runs.sh status <full-sha>    one line per run; exit 0
#   bash scripts/gh-runs.sh pending <full-sha>   count NOT completed -> stdout
#   bash scripts/gh-runs.sh cited  <full-sha>    0 only if >=1 run and ALL success
#
# EXIT CODES
#   0  answered
#   2  REFUSED / CANNOT TELL  (short sha, no gh, dead API, failed query)
#   1  answered, and the answer is "not cited"   (`cited` only)
#
# ⚠️ FAIL-CLOSED ON CANNOT-TELL. A broken instrument and a quiet branch produce
# the same zero, so anything that cannot be established exits 2 rather than
# looking like an all-clear.
# ============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/inflight.sh
. "$HERE/lib/inflight.sh"

die2() { printf '🔴 gh-runs: %s\n' "$*" >&2; exit 2; }

require_full_sha() {
  local sha="${1:-}"
  [ -n "$sha" ] || die2 "no sha given. Pass the FULL 40-character sha (git rev-parse HEAD)."
  case "$sha" in *[!0-9a-fA-F]*) die2 "sha '$sha' is not hexadecimal." ;; esac
  if [ "${#sha}" -ne 40 ]; then
    die2 "REFUSED — sha '$sha' is ${#sha} characters, not 40.
       \`gh run list --commit\` returns [] for ANY abbreviated sha, with exit 0
       and no warning. That is a FALSE ALL-CLEAR, not an empty result.
       Use: \$(git rev-parse HEAD)"
  fi

  # ⚠️ FULL-LOOKING IS NOT FULL. The length check above passes any 40 hex
  # characters, including a short sha somebody PADDED or mistyped. To the
  # runs API a fabricated sha and a real sha whose runs have not started are
  # THE SAME ANSWER — no rows — so a polling caller waits forever on a commit
  # that does not exist.
  #
  # Measured 2026-08-16: a batch citation was polled against
  # cc6d9ee8ceff34c14eafcdf22ea59923eec4facf while origin/main was
  # cc6d9ee81287036bbf1e97ef8cbf88eaae719cef — same 8 characters, different
  # commit. `cited` returned exit 1 for BOTH the fabricated sha and the real
  # one with runs pending. Indistinguishable. This is the second time a
  # fabricated sha has been caught in this programme; the first was caught by
  # check-citation.sh, which already verifies existence.
  #
  # So: EXIST-CHECK, and fail as 2 = CANNOT TELL rather than 1 = not cited.
  if git rev-parse --git-dir >/dev/null 2>&1; then
    if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then
      git fetch --quiet origin 2>/dev/null || true
      if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then
        die2 "NO SUCH COMMIT — '$sha' is not a commit in this repository.
       It is 40 hex characters, so it LOOKS full. It is not real.
       A fabricated sha and a real sha with pending runs both return NO ROWS,
       so this is reported as CANNOT TELL (2), never as 'not cited' (1).
       Read it, do not build it: \$(git rev-parse HEAD)"
      fi
    fi
  fi
}

# Prove the runs API answers for this repo before believing any zero from it.
require_working_api() {
  inflight_require_gh || die2 "'gh' is not on PATH — CANNOT TELL, not an all-clear."
  inflight_positive_control || die2 "the runs API returned nothing for this repository — a zero from it proves nothing."
}

cmd="${1:-}"; sha="${2:-}"
# ⚠️ THE COMMAND IS VALIDATED BEFORE THE SHA, DELIBERATELY. Validating the sha
# first makes a wrong VERB report a sha complaint: `gh-runs.sh list --commit
# <sha>` (the shape muscle-memory reaches for) refused with "'--commit' is not
# hexadecimal", which is true, fail-closed, and names the wrong problem.
case "$cmd" in
  status|pending|cited) ;;
  *) die2 "unknown command '${cmd:-}'. Use: status | pending | cited <FULL-40-char-sha>
       This wrapper takes a BARE sha, never a \`--commit\` flag." ;;
esac
require_full_sha "$sha"
require_working_api

rows=$(gh run list --commit "$sha" --limit 30 --json name,status,conclusion 2>/dev/null) \
  || die2 "the runs query failed for $sha."
[ -n "$rows" ] || die2 "the runs query returned nothing readable for $sha."

case "$cmd" in
  status)
    echo "$rows" | jq -r '.[] | "  \(.name): \(.status) \(.conclusion // "")"'
    ;;
  pending)
    echo "$rows" | jq -r '[.[]|select(.status!="completed")]|length'
    ;;
  cited)
    total=$(echo "$rows" | jq -r 'length')
    ok=$(echo "$rows" | jq -r '[.[]|select(.conclusion=="success")]|length')
    # ⚠️ A ZERO-RUN COMMIT IS NOT CITED. Without this, a sha nothing ever ran
    # against reports "all runs succeeded" — vacuously, which is the same
    # false all-clear one layer up.
    if [ "$total" -lt 1 ]; then
      echo "NOT CITED — no runs exist for $sha (vacuous, not clean)."
      exit 1
    fi
    echo "$ok of $total success"
    [ "$ok" -eq "$total" ] || exit 1
    ;;
  *)
    die2 "unknown command '${cmd:-}'. Use: status | pending | cited"
    ;;
esac
