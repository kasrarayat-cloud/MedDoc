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
#   sweep_guard <label> <count> <bound> <declaration-variable-name> <window-file>
#     0 = not a sweep, or a sweep DECLARED with a reason (echoed to stderr)
#     1 = REFUSED
#
# ⚠️ THE BOUND IS COUNTED ACROSS CALLS, NOT PER CALL, AND NOT BY PROCESS NAME
# (2026-09-29 refutation, F2). The first version refused a call naming more than
# <bound> paths, or one whose ancestor was NAMED find/xargs/parallel/fd. That was
# defeated three ways with no declaration: `busybox xargs` (the process is named
# busybox), xargs run through a link with another name, and `xargs … setsid -f`
# (the parent becomes pid 1). A name is a claim a process makes about itself.
#
# So every undeclared call appends its path count to <window-file> under an
# exclusive lock, and a call is a sweep when EITHER holds:
#   * it names more than <bound> paths itself;
#   * its paths plus every undeclared path counted in <window-file> within the
#     last SWEEP_GUARD_WINDOW_SECONDS exceed <bound> — whatever drives the calls:
#     xargs by any name, setsid, a shell `for` loop, a script, or nothing at all.
# The ancestry check is KEPT as an early refusal — it stops `find -exec … \;` at
# the first file instead of the seventeenth — but nothing relies on it.
#
# The window file is private state OUTSIDE the scratch sandbox: its directory is
# yours and has no group/other bit, the file is 0600, yours, one link, never a
# symlink. A window that cannot be read, locked or trusted is CANNOT TELL, and
# CANNOT TELL refuses. Declared calls are recorded and do not spend the bound.
#
# ⚠️ HONEST LIMITS. Up to <bound> paths per window pass undeclared, whatever drives
# them — the bound is a rate, so the first <bound> files of a sweep are taken. A
# caller that names a fresh window for every call (a fresh ledger each time, or a
# fresh XDG_STATE_HOME) is not bounded; that is a deliberate construction, not an
# accident, and is outside what this guard can see.
#
# The override is the programme's DECLARATION, the same check as
# DECLARE_CANCELLATION (`inflight_declaration_ok`, sourced, not copied): prose of
# at least 12 visible characters, never a bare 1/true/yes.
# ============================================================================

_SWEEP_GUARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
if [ -z "${_SWEEP_GUARD_DIR:-}" ] || [ ! -r "$_SWEEP_GUARD_DIR/inflight.sh" ]; then
  sweep_guard() {
    echo "🔴 ${1:-sweep-guard}: CANNOT TELL — lib/inflight.sh (the declaration check) is missing; refusing." >&2
    return 1
  }
  sweep_guard_state_file() { return 1; }
  return 0 2>/dev/null || exit 1
fi
# shellcheck source=inflight.sh
. "$_SWEEP_GUARD_DIR/inflight.sh"

SWEEP_GUARD_DRIVERS=" find xargs parallel fd fdfind "
SWEEP_GUARD_WINDOW_SECONDS=300

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

# True when <path> (resolved) is the scratch sandbox or under it.
_sweep_guard_in_sandbox() {
  local real
  real="$(realpath -m -- "$1" 2>/dev/null)" || return 0   # cannot resolve: treat as inside (refuse)
  [ -n "$real" ] || return 0
  case "$real/" in "/tmp/claude-${EUID}/"*) return 0 ;; esac
  return 1
}

# sweep_guard_state_file <name> — the per-uid window file for a caller with no
# ledger of its own: ${XDG_STATE_HOME:-$HOME/.local/state}/scratch-sweep-guard/<name>.window
# Creates the directory 0700 if absent. Prints the path; 1 = CANNOT TELL.
sweep_guard_state_file() {
  local name="$1" base dir
  base="${XDG_STATE_HOME:-}"
  if [ -z "$base" ]; then
    if [ -z "${HOME:-}" ]; then
      echo "🔴 CANNOT TELL — neither XDG_STATE_HOME nor HOME is set, so there is nowhere to count calls." >&2
      return 1
    fi
    base="$HOME/.local/state"
  fi
  case "$base" in
    /*) ;;
    *) echo "🔴 CANNOT TELL — the state directory '$base' is not an absolute path." >&2; return 1 ;;
  esac
  dir="$base/scratch-sweep-guard"
  if _sweep_guard_in_sandbox "$dir"; then
    echo "🔴 CANNOT TELL — the sweep window $dir is inside /tmp/claude-${EUID}/, where a sweep can reach it." >&2
    return 1
  fi
  if [ ! -e "$dir" ] && [ ! -L "$dir" ]; then
    ( umask 077 && mkdir -p -- "$dir" ) 2>/dev/null || {
      echo "🔴 CANNOT TELL — cannot create the sweep window directory $dir." >&2
      return 1; }
  fi
  printf '%s\n' "$dir/$name.window"
}

# The window, under an exclusive lock: every return path closes the fd.
_sweep_guard_private_mode() {  # <octal mode> -> 0 when no group/other bit is set
  case "$1" in ''|*[!0-7]*) return 1 ;; esac
  [ $(( 8#$1 & 63 )) -eq 0 ]   # 63 = octal 77: every group and other bit
}

sweep_guard() {
  local label="$1" count="$2" bound="$3" declvar="$4" window="${5:-}"
  local decl="${!declvar:-}" why="" driver rc now dir fd="" old_umask recent=0 t c f extra line_no=0 bad="" lines
  local d_uid d_mode d_type i_uid i_mode i_links i_type i_dev i_ino path_id
  case "$count" in ''|*[!0-9]*) echo "🔴 $label: CANNOT TELL — bad path count '$count'; refusing." >&2; return 1 ;; esac
  case "$bound" in ''|*[!0-9]*) echo "🔴 $label: CANNOT TELL — bad bound '$bound'; refusing." >&2; return 1 ;; esac
  if [ -z "$window" ]; then
    echo "🔴 $label: CANNOT TELL — no sweep window was named, so calls cannot be counted; refusing." >&2
    return 1
  fi
  command -v flock >/dev/null 2>&1 || {
    echo "🔴 $label: CANNOT TELL — no flock on PATH, so the sweep window cannot be locked; refusing." >&2
    return 1; }
  dir="$(dirname -- "$window")"
  if _sweep_guard_in_sandbox "$dir"; then
    echo "🔴 $label: CANNOT TELL — the sweep window $window is inside /tmp/claude-${EUID}/; refusing." >&2
    return 1
  fi
  IFS=: read -r d_uid d_mode d_type <<< "$(stat -c '%u:%a:%F' -- "$dir" 2>/dev/null)"
  if [ -L "$dir" ] || [ "$d_uid" != "$EUID" ] || [ "$d_type" != "directory" ] || ! _sweep_guard_private_mode "$d_mode"; then
    echo "🔴 $label: CANNOT TELL — the sweep window directory $dir is not a private directory of yours; refusing." >&2
    return 1
  fi
  if [ -L "$window" ]; then
    echo "🔴 $label: CANNOT TELL — the sweep window $window is a symbolic link; refusing." >&2
    return 1
  fi
  old_umask="$(umask)"
  umask 077
  # ⚠️ GROUPED: a bare `exec {fd}>>file 2>/dev/null` would ALSO send this shell's
  # stderr to /dev/null for good, and every refusal after it would be silent.
  { exec {fd}>>"$window"; } 2>/dev/null
  umask "$old_umask"
  if [ -z "$fd" ]; then
    echo "🔴 $label: CANNOT TELL — the sweep window $window cannot be opened; refusing." >&2
    return 1
  fi
  IFS=: read -r i_uid i_mode i_links i_type i_dev i_ino <<< "$(stat -L -c '%u:%a:%h:%F:%d:%i' "/dev/fd/$fd" 2>/dev/null)"
  path_id="$(stat -c '%d:%i' -- "$window" 2>/dev/null)"
  if [ -z "$i_ino" ] || [ "$path_id" != "$i_dev:$i_ino" ] || [ "$i_uid" != "$EUID" ] || [ "$i_links" != 1 ] \
     || ! _sweep_guard_private_mode "$i_mode"; then
    exec {fd}>&-
    echo "🔴 $label: CANNOT TELL — the sweep window $window is not a private (0600) file of yours with one link; refusing." >&2
    return 1
  fi
  case "$i_type" in
    'regular file'|'regular empty file') ;;
    *) exec {fd}>&-
       echo "🔴 $label: CANNOT TELL — the sweep window $window is not a regular file; refusing." >&2
       return 1 ;;
  esac
  if ! flock -x -w 60 "$fd"; then
    exec {fd}>&-
    echo "🔴 $label: CANNOT TELL — the sweep window $window could not be locked within 60s; refusing." >&2
    return 1
  fi
  printf -v now '%(%s)T' -1
  while IFS=' ' read -r t c f extra; do
    line_no=$((line_no + 1))
    # Decimal only, bounded, no leading zero: bash arithmetic reads 010 as octal
    # and wraps past 2^63, and either would let a count shrink the sum.
    case "$t" in ''|*[!0-9]*|0?*) bad="$line_no"; break ;; esac
    case "$c" in ''|*[!0-9]*|0?*) bad="$line_no"; break ;; esac
    { [ "${#t}" -le 12 ] && [ "${#c}" -le 9 ]; } || { bad="$line_no"; break; }
    case "$f" in u|d) ;; *) bad="$line_no"; break ;; esac
    [ -z "$extra" ] || { bad="$line_no"; break; }
    # A line from the future (a clock step back) counts: that direction refuses.
    if [ "$f" = u ] && [ "$t" -gt $((now - SWEEP_GUARD_WINDOW_SECONDS)) ]; then
      recent=$((recent + 10#$c))
    fi
  done < "$window"
  lines="$(wc -l < "$window" 2>/dev/null)"
  lines="${lines//[[:space:]]/}"
  if [ -z "$bad" ] && [ "$lines" != "$line_no" ]; then
    bad="$line_no (read $line_no of ${lines:-an unknown number of} lines)"
  fi
  # A last line with no newline (a write cut short) is skipped by `read` and not
  # counted by `wc -l` alike, so it would vanish from the sum: CANNOT TELL.
  if [ -z "$bad" ] && [ -s "$window" ] && [ "$(tail -c 1 -- "$window" | od -An -tx1 | tr -d ' \n')" != "0a" ]; then
    bad="$((line_no + 1)) (the last line has no newline)"
  fi
  if [ -n "$bad" ]; then
    exec {fd}>&-
    echo "🔴 $label: CANNOT TELL — line $bad of the sweep window $window is not '<epoch> <count> u|d'; refusing." >&2
    return 1
  fi
  if [ "$count" -gt "$bound" ]; then
    why="$count paths in one call (the bound is $bound)"
  elif [ $((recent + count)) -gt "$bound" ]; then
    why="$count paths in this call and $recent undeclared in the last ${SWEEP_GUARD_WINDOW_SECONDS}s (the bound is $bound per ${SWEEP_GUARD_WINDOW_SECONDS}s, whatever process drives the calls)"
  fi
  driver="$(sweep_guard_driver "$$")"; rc=$?
  case "$rc" in
    0) why="${why:+$why; }driven by $driver" ;;
    1) : ;;
    *) why="${why:+$why; }CANNOT TELL whether find/xargs drives this call (process ancestry unreadable)" ;;
  esac
  if [ -z "$why" ]; then
    printf '%s %s u\n' "$now" "$count" >&"$fd" || {
      exec {fd}>&-; echo "🔴 $label: CANNOT TELL — the sweep window $window cannot be written; refusing." >&2; return 1; }
    exec {fd}>&-
    return 0
  fi
  if [ -z "$decl" ]; then
    exec {fd}>&-
    echo "🔴 $label: REFUSED — this call has the shape of a whole-tree sweep: $why." >&2
    echo "   A sweep cannot tell your scratch from another agent's: on 2026-09-29 one shredded" >&2
    echo "   30 files other agents owned and another 6,537, its own logs included." >&2
    echo "   Record what you create (bash scripts/scratch-ledger.sh record …) and reap only that" >&2
    echo "   (bash scripts/reap-recorded-scratch.sh <ledger>). If a bulk call is genuinely right," >&2
    echo "   say why: $declvar=\"<reason, 12+ visible chars>\"." >&2
    return 1
  fi
  if ! inflight_declaration_ok "$decl"; then
    exec {fd}>&-
    echo "🔴 $label: REFUSED ($declvar)" >&2
    return 1
  fi
  printf '%s %s d\n' "$now" "$count" >&"$fd" || {
    exec {fd}>&-; echo "🔴 $label: CANNOT TELL — the sweep window $window cannot be written; refusing." >&2; return 1; }
  exec {fd}>&-
  echo "⚠️  $label: BULK CALL DECLARED ($why) — $declvar: $decl" >&2
  return 0
}
