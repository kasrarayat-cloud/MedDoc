#!/usr/bin/env bash
# ============================================================================
# THE TWO-VIEW IN-FLIGHT CHECK — sourced, never duplicated.
# ----------------------------------------------------------------------------
# One implementation, two callers: `scripts/hooks/pre-push` (the PUSH side) and
# `scripts/merge-pr.sh` (the MERGE side). They guard the same hazard from the two
# directions GitHub can reach a ref, and a second copy of this logic would drift
# from the first the day one of them is fixed.
#
# ⚠️ BOTH VIEWS, AND NEITHER IS REDUNDANT. `gh run list --commit` under-reports in
# the propagation window right after a push — measured: `[]` from --commit while
# --branch showed three runs pending on that very SHA, seconds apart. `--branch`
# is the view that is right first. A zero is believed only when both agree.
#
# ⚠️ EVERY ZERO IS POSITIVE-CONTROLLED. A broken or unauthenticated `gh` returns
# the same empty list as a quiet ref, so callers confirm the runs API answers for
# this repository at all before believing anything it says.
#
# Exit convention throughout: 0 = fine, 1 = CANNOT TELL (callers must refuse).
# ----------------------------------------------------------------------------
# ⚠️ SINCE F14-b (2026-08-17) THE TRANSPORT IS `lib/runs-api.sh`, NOT `gh run
# list`. That is the whole item, and the reason is measured rather than
# defensive: on 2026-08-17 GitHub's repo-wide `/actions/runs` route 404'd for
# this repository for hours while every other Actions route answered. `gh run
# list` calls that one route underneath, so BOTH doors this file serves — the
# `pre-push` hook and `merge-pr.sh` — refused every push and every merge for the
# duration. F14-a routed the CITATION door around it and deliberately left these
# two, because getting them wrong in an unattended session means nothing can be
# merged or pushed to fix it. This is that item, landed on its own.
#
# ⚠️ THE REFUSALS WERE CORRECT AND ARE NOT WHAT CHANGED. A `gh` that is absent,
# unauthenticated, or answering nothing still exits 1 = CANNOT TELL and both
# doors still refuse. What changed is that a repo-wide outage alone no longer
# produces that state, because a SECOND INDEX OVER THE SAME TABLE is tried
# before anyone concludes the instrument is blind. A fallback that returns the
# same run objects from a different route is a transport, not a loosening.
#
# ⚠️ AND THE DEGRADATION IS ANNOUNCED, NOT SWALLOWED — see INFLIGHT_DEGRADED
# below. The branch view has no per-commit coverage control (nothing indexes a
# BRANCH's runs by commit), so in fallback mode its count is a FLOOR. Callers
# print that fact. A number that is quietly a floor is the shape this repo has
# paid for more than once.
# ============================================================================

# ⚠️ SOURCED FAIL-CLOSED, AND ANCHORED TO THIS FILE. A lib that silently skipped
# its own transport because a file moved would be worse than no lib — the same
# reasoning the pre-push hook applies to sourcing THIS file.
_INFLIGHT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
if [ -z "${_INFLIGHT_LIB_DIR:-}" ] || [ ! -r "$_INFLIGHT_LIB_DIR/runs-api.sh" ]; then
  echo "CANNOT TELL — lib/runs-api.sh is missing or unreadable; the in-flight" >&2
  echo "              check has no transport. Refusing rather than guessing." >&2
  inflight_declaration_ok() { return 1; }
  inflight_require_gh()     { return 1; }
  inflight_positive_control(){ return 1; }
  inflight_count()          { return 1; }
  inflight_total()          { echo 0; }
  return 0 2>/dev/null || exit 1
fi
# shellcheck source=runs-api.sh
. "$_INFLIGHT_LIB_DIR/runs-api.sh"

# ⚠️ THE REPOSITORY IS READ FROM THE REMOTE, NEVER GUESSED FROM A DIRECTORY NAME.
# On 2026-08-17 a session probing the runs API queried `meddoc-pro` — the
# directory — when the repository is `MedDoc`, and got a 404 indistinguishable
# from the outage it was investigating. `gh repo view` resolves the configured
# remote, so it cannot be wrong about which repository this is.
# ⚠️ IT ANSWERS ON STDOUT AND CACHES NOTHING, AND THAT IS DELIBERATE. Every
# call site invokes it as `repo="$(inflight_repo)"`, which is a COMMAND
# SUBSTITUTION, which is a SUBSHELL — so an assignment made inside it is
# discarded and a cache global would be dead while LOOKING like an optimisation.
# That is the exact defect `runs-api.sh`'s header records paying a round for
# (`RUNS_API_MODE`), and writing a second one here with a confident comment
# beside it is how the lesson fails to take. `gh repo view` is a local metadata
# read; two of them per push is not a cost worth a broken abstraction.
#
# `INFLIGHT_REPO` is honoured if a CALLER exports it — which is how a proof
# pins the repository without touching the remote — but nothing here sets it.
inflight_repo() {
  if [ -n "${INFLIGHT_REPO:-}" ]; then printf '%s' "$INFLIGHT_REPO"; return 0; fi
  local r
  r="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
  if [ -z "$r" ]; then
    echo "CANNOT TELL — cannot determine which repository this is, so no runs" >&2
    echo "              query can be scoped. This is a CANNOT-TELL, not a clear." >&2
    return 1
  fi
  printf '%s' "$r"
}

# Refuse a declaration that is a bypass token rather than a reason.
#   0 = acceptable (or empty, i.e. no declaration offered), 1 = refuse
#
# ⚠️ COUNTED IN VISIBLE CHARACTERS, NOT IN LENGTH (2026-09-29). The length test
# accepted twelve spaces — a declaration that says nothing and passes as prose,
# echoed to the log as a blank. So the count is of PRINTABLE ASCII non-space
# characters (0x21-0x7E), taken by `tr` in the C locale so no locale can widen it:
# spaces, tabs, newlines, no-break and zero-width spaces all count ZERO. Other
# characters may appear, but they never make up the twelve.
inflight_declaration_ok() {
  local decl="${1:-}" visible
  [ -z "$decl" ] && return 0
  case "${decl,,}" in
    1|true|yes|y|on|force|skip)
      echo "REFUSED — the declaration must be a REASON, not '$decl'." >&2
      echo "          An audit trail's why is somebody's words or nothing." >&2
      return 1 ;;
  esac
  visible="$(printf '%s' "$decl" | LC_ALL=C tr -cd '\041-\176' | LC_ALL=C wc -c)" || visible=""
  visible="${visible//[[:space:]]/}"
  case "$visible" in
    ''|*[!0-9]*)
      echo "REFUSED — CANNOT TELL how many visible characters the declaration has." >&2
      return 1 ;;
  esac
  if [ "$visible" -lt 12 ]; then
    echo "REFUSED — the declaration has $visible visible characters (printable ASCII, not" >&2
    echo "          counting spaces or blanks of any kind); a declaration is prose of at least 12." >&2
    return 1
  fi
  return 0
}

inflight_require_gh() {
  command -v gh >/dev/null 2>&1 && return 0
  echo "CANNOT TELL — 'gh' is not on PATH, so in-flight runs cannot be checked." >&2
  echo "              This is a CANNOT-TELL, not an all-clear." >&2
  return 1
}

# Prove the instrument works before believing a zero from it.
#
# ⚠️ IT NOW CONTROLS THE TRANSPORT, NOT ONE ROUTE. `runs_api_control` tries the
# repo-wide route and, if it does not answer, sums the per-workflow totals — so
# a repo-wide outage no longer makes the control fail and take both doors down
# with it. A genuinely blind instrument (no `gh`, no `jq`, no auth, neither
# route answering, or a repository that truly reports zero runs) still fails,
# which is the state this control exists to detect.
inflight_positive_control() {
  local repo n
  repo="$(inflight_repo)" || return 1
  n="$(runs_api_control "$repo")" || {
    echo "CANNOT TELL — no runs transport answers for $repo, so a zero from it" >&2
    echo "              proves nothing (positive control failed)." >&2
    echo "              Check 'gh auth status'." >&2
    return 1; }
  [ "${n:-0}" -ge 1 ] && return 0
  echo "CANNOT TELL — $repo reports zero workflow runs in total, so this" >&2
  echo "              instrument cannot distinguish quiet from broken." >&2
  return 1
}

# inflight_count <branch> <full-40-char-sha>
# Sets INFLIGHT_BY_COMMIT / INFLIGHT_BY_BRANCH. 0 = counted, 1 = cannot tell.
#
# Also sets, for callers to REPORT rather than to decide on:
#   INFLIGHT_TRANSPORT  "repo-wide" | "per-workflow" | "mixed"
#   INFLIGHT_DEGRADED   1 when either view came from the fallback
#   INFLIGHT_NOTE       the honest limit, in words, or empty
INFLIGHT_BY_COMMIT=0
INFLIGHT_BY_BRANCH=0
INFLIGHT_TRANSPORT="repo-wide"
INFLIGHT_DEGRADED=0
INFLIGHT_NOTE=""
inflight_count() {
  local branch="${1:-}" sha="${2:-}" repo pc pb tc tb
  # ⚠️ FULL 40 CHARS OR NOTHING — an abbreviated sha filters to nothing on the
  # runs routes just as it does through `gh run list`, with no error either way.
  # A false all-clear, and this is the door where a false all-clear cancels
  # somebody's evidence.
  if [ "${#sha}" -ne 40 ]; then
    echo "CANNOT TELL — sha '$sha' is not 40 characters." >&2
    return 1
  fi
  repo="$(inflight_repo)" || return 1

  pc="$(runs_api_for_sha "$repo" "$sha" 100)" || {
    echo "CANNOT TELL — no runs transport answered for commit $sha." >&2; return 1; }
  pb="$(runs_api_for_branch "$repo" "$branch" 100)" || {
    echo "CANNOT TELL — no runs transport answered for branch '$branch'." >&2; return 1; }

  # ⚠️ COUNTED OVER `workflow_runs`, AND NOT TRUNCATION-REFUSED. `?branch=main`
  # reports thousands of runs in total_count against a 100-row page, so a
  # sum==total arm here would refuse EVERY push to main — the check would be
  # perfectly rigorous and permanently closed. Both routes return newest-first,
  # so a run that is not `completed` is among the newest by construction; the
  # predecessor of this code relied on exactly the same property with a tighter
  # window (`--limit 20`). Stated so nobody reads the absence as an oversight.
  INFLIGHT_BY_COMMIT=$(printf '%s' "$pc" | jq -r '[.workflow_runs[]|select(.status!="completed")]|length' 2>/dev/null)
  INFLIGHT_BY_BRANCH=$(printf '%s' "$pb" | jq -r '[.workflow_runs[]|select(.status!="completed")]|length' 2>/dev/null)
  if [ -z "${INFLIGHT_BY_COMMIT:-}" ] || [ -z "${INFLIGHT_BY_BRANCH:-}" ]; then
    echo "CANNOT TELL — a runs payload for '$branch' was not readable." >&2
    return 1
  fi

  tc="$(printf '%s' "$pc" | jq -r '._transport // "unknown"' 2>/dev/null)"
  tb="$(printf '%s' "$pb" | jq -r '._transport // "unknown"' 2>/dev/null)"
  INFLIGHT_NOTE=""
  INFLIGHT_DEGRADED=0
  if [ "$tc" = "repo-wide" ] && [ "$tb" = "repo-wide" ]; then
    INFLIGHT_TRANSPORT="repo-wide"
  else
    INFLIGHT_DEGRADED=1
    if [ "$tc" = "$tb" ]; then INFLIGHT_TRANSPORT="$tc"; else INFLIGHT_TRANSPORT="mixed"; fi
    # ⚠️ THE TWO VIEWS DEGRADE DIFFERENTLY, AND SAYING SO IS THE POINT.
    # The COMMIT view carries `runs-api.sh`'s check-suites coverage control, so
    # in fallback mode it is still complete or it refuses. The BRANCH view has
    # no such control — nothing indexes a branch's runs independently of the
    # workflow enumeration — so its count is a FLOOR and an under-report is the
    # direction that costs somebody a run.
    INFLIGHT_NOTE="⚠️ per-workflow FALLBACK transport (commit=$tc, branch=$tb). The --commit count is coverage-controlled; the --branch count is a FLOOR."
  fi
  return 0
}

inflight_total() { echo $(( INFLIGHT_BY_COMMIT + INFLIGHT_BY_BRANCH )); }
