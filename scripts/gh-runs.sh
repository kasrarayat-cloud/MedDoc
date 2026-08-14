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
}

# Prove the runs API answers for this repo before believing any zero from it.
require_working_api() {
  inflight_require_gh || die2 "'gh' is not on PATH — CANNOT TELL, not an all-clear."
  inflight_positive_control || die2 "the runs API returned nothing for this repository — a zero from it proves nothing."
}

cmd="${1:-}"; sha="${2:-}"
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
