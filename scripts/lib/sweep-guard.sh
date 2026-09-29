#!/usr/bin/env bash
# ============================================================================
# THE SWEEP GUARD — sourced, never duplicated.
# ----------------------------------------------------------------------------
# One implementation, two callers: `scripts/reap-session-scratch.sh` (destroys
# named paths) and `scripts/lib/scratch_ledger.py` via `scratch-ledger.sh record`
# (claims named paths as "mine, disposable"). Both are safe one deliberate path
# at a time and catastrophic when a tree walk feeds them.
#
# ⚠️ WHY — 2026-09-29, one session, two incidents, the same shape:
#
#   find <whole session scratchpad> -type f | xargs bash scripts/reap-session-scratch.sh
#       -> a subagent shredded 30 files OTHER agents had written
#   find ... -print0 | xargs -0 -n 200 bash scripts/reap-session-scratch.sh   (x3)
#       -> the lead shredded 6,537 files, the cleanup's own lists and logs included
#
# Every path was inside the sandbox, so every per-path refusal passed. What was
# wrong was not any one path; it was that nobody had decided about any of them.
#
#   sweep_guard <label> <count> <bound> <declaration-variable-name>
#     0 = not a sweep, or a sweep DECLARED with a reason (echoed to stderr)
#     1 = REFUSED
#
# A call is treated as a sweep when EITHER holds:
#   * it names more than <bound> paths (xargs batches by the thousand, or -n 200);
#   * a `find`, `xargs`, `parallel`, `fd` or `fdfind` process is an ANCESTOR —
#     which catches `find -exec … {} \;` and `xargs -n 1`, where the count is 1.
# ⚠️ AND IT IS FAIL-CLOSED ON CANNOT-TELL: unreadable process ancestry is treated
# as a sweep. ⚠️ HONEST LIMIT: a shell loop over `find` output
# (`for f in $(find …); do …; done`) leaves no ancestor to see; that shape is
# caught only by the recorded reaper, which never takes a path it did not record.
#
# The override is the programme's DECLARATION, the same check as
# DECLARE_CANCELLATION (`inflight_declaration_ok`, sourced, not copied): prose of
# at least 12 characters, never a bare 1/true/yes.
# ============================================================================

_SWEEP_GUARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
if [ -z "${_SWEEP_GUARD_DIR:-}" ] || [ ! -r "$_SWEEP_GUARD_DIR/inflight.sh" ]; then
  sweep_guard() {
    echo "🔴 ${1:-sweep-guard}: CANNOT TELL — lib/inflight.sh (the declaration check) is missing; refusing." >&2
    return 1
  }
  return 0 2>/dev/null || exit 1
fi
# shellcheck source=inflight.sh
. "$_SWEEP_GUARD_DIR/inflight.sh"

SWEEP_GUARD_DRIVERS=" find xargs parallel fd fdfind "

# Walk the ancestors of <pid> (not <pid> itself). Prints "<comm> (pid N)" for the
# nearest sweep driver. 0 = found, 1 = none, 2 = CANNOT TELL.
sweep_guard_driver() {
  local pid="$1" hops=0 line rest state ppid comm
  while [ "$hops" -lt 128 ]; do
    line=""
    { IFS= read -r line < "/proc/$pid/stat"; } 2>/dev/null || return 2
    [ -n "$line" ] || return 2
    rest="${line##*) }"
    read -r state ppid _ <<< "$rest"
    case "$ppid" in ''|*[!0-9]*) return 2 ;; esac
    [ "$ppid" -eq 0 ] && return 1
    comm=""
    { IFS= read -r comm < "/proc/$ppid/comm"; } 2>/dev/null || return 2
    case "$SWEEP_GUARD_DRIVERS" in
      *" $comm "*) echo "$comm (pid $ppid)"; return 0 ;;
    esac
    [ "$ppid" -le 1 ] && return 1
    pid="$ppid"
    hops=$((hops + 1))
  done
  return 2
}

sweep_guard() {
  local label="$1" count="$2" bound="$3" declvar="$4"
  local decl="${!declvar:-}" why="" driver rc
  case "$count" in ''|*[!0-9]*) echo "🔴 $label: CANNOT TELL — bad path count '$count'; refusing." >&2; return 1 ;; esac
  if [ "$count" -gt "$bound" ]; then
    why="$count paths in one call (the bound is $bound)"
  fi
  driver="$(sweep_guard_driver "$$")"; rc=$?
  case "$rc" in
    0) why="${why:+$why; }driven by $driver" ;;
    1) : ;;
    *) why="${why:+$why; }CANNOT TELL whether find/xargs drives this call (process ancestry unreadable)" ;;
  esac
  [ -z "$why" ] && return 0
  if [ -z "$decl" ]; then
    echo "🔴 $label: REFUSED — this call has the shape of a whole-tree sweep: $why." >&2
    echo "   A sweep cannot tell your scratch from another agent's: on 2026-09-29 one shredded" >&2
    echo "   30 files other agents owned and another 6,537, its own logs included." >&2
    echo "   Record what you create (bash scripts/scratch-ledger.sh record …) and reap only that" >&2
    echo "   (bash scripts/reap-recorded-scratch.sh <ledger>). If a bulk call is genuinely right," >&2
    echo "   say why: $declvar=\"<reason, 12+ chars>\"." >&2
    return 1
  fi
  inflight_declaration_ok "$decl" || { echo "🔴 $label: REFUSED ($declvar)" >&2; return 1; }
  echo "⚠️  $label: BULK CALL DECLARED ($why) — $declvar: $decl" >&2
  return 0
}
