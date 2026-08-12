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
# ============================================================================

# Refuse a declaration that is a bypass token rather than a reason.
#   0 = acceptable (or empty, i.e. no declaration offered), 1 = refuse
inflight_declaration_ok() {
  local decl="${1:-}"
  [ -z "$decl" ] && return 0
  case "${decl,,}" in
    1|true|yes|y|on|force|skip)
      echo "REFUSED — the declaration must be a REASON, not '$decl'." >&2
      echo "          An audit trail's why is somebody's words or nothing." >&2
      return 1 ;;
  esac
  if [ "${#decl}" -lt 12 ]; then
    echo "REFUSED — the declaration is ${#decl} chars; a declaration is prose." >&2
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
inflight_positive_control() {
  local n
  n=$(gh run list --limit 1 --json databaseId --jq 'length' 2>/dev/null)
  [ "${n:-0}" -ge 1 ] && return 0
  echo "CANNOT TELL — the runs API returned nothing for this repository, so a" >&2
  echo "              zero from it proves nothing (positive control failed)." >&2
  echo "              Check 'gh auth status'." >&2
  return 1
}

# inflight_count <branch> <full-40-char-sha>
# Sets INFLIGHT_BY_COMMIT / INFLIGHT_BY_BRANCH. 0 = counted, 1 = cannot tell.
INFLIGHT_BY_COMMIT=0
INFLIGHT_BY_BRANCH=0
inflight_count() {
  local branch="${1:-}" sha="${2:-}"
  # ⚠️ FULL 40 CHARS OR NOTHING — `gh run list --commit <SHORT-sha>` returns []
  # for ANY abbreviation, exit 0, no warning. A false all-clear.
  if [ "${#sha}" -ne 40 ]; then
    echo "CANNOT TELL — sha '$sha' is not 40 characters." >&2
    return 1
  fi
  INFLIGHT_BY_COMMIT=$(gh run list --commit "$sha" --limit 20 --json status \
                         --jq '[.[]|select(.status!="completed")]|length' 2>/dev/null)
  INFLIGHT_BY_BRANCH=$(gh run list --branch "$branch" --limit 20 --json status \
                         --jq '[.[]|select(.status!="completed")]|length' 2>/dev/null)
  if [ -z "${INFLIGHT_BY_COMMIT:-}" ] || [ -z "${INFLIGHT_BY_BRANCH:-}" ]; then
    echo "CANNOT TELL — a runs query failed for '$branch'." >&2
    return 1
  fi
  return 0
}

inflight_total() { echo $(( INFLIGHT_BY_COMMIT + INFLIGHT_BY_BRANCH )); }
