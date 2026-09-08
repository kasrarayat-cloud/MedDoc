#!/usr/bin/env bash
# ============================================================================
# REAP A LENS SANDBOX — and REFUSE one that is still somebody's.
#   0 = reaped   1 = REFUSED (nothing removed)
# ----------------------------------------------------------------------------
# ⚠️ THIS SCRIPT USED TO CHECK A FILENAME PREFIX AND A DIRECTORY, THEN
# `worktree remove --force`. On a box where three sessions share one account
# that is a loaded gun: it would remove a PEER'S LIVE SANDBOX mid-round, and the
# lens would find its tree gone with no error anyone could attribute.
#
# #206 specified a marker; **#213 amended it** and this implements the amendment.
#
# ── THE MARKER: SESSION ID + START-TIME, NEVER `$$` (#213) ──────────────────
# `$$` in a tool shell is a FRESH SUBSHELL. The pid it records belongs to a
# process that was already dead when the file was written, so an aliveness check
# against it answers **"dead"** — the direction that costs somebody their tree.
# Measured first-hand while building this: `CLAUDE_PID=2204890`, `$$=3555429`.
#
# The START-TIME (field 22 of `/proc/<pid>/stat`) binds the pid to an identity.
# A bare pid is reused, and a reused pid reads as ALIVE for a session that ended
# hours ago.
#
# ── THE REFUSAL, AND THE `OR` IS LOAD-BEARING (#213) ────────────────────────
#
#   REFUSE when the marker is FRESH **OR** when ANY process holds the tree.
#
# Either condition alone is a guard with a hole, and #213 names both:
#   · marker-only  misses a live worker whose session stamped its marker long ago
#   · process-only misses a session BETWEEN COMMANDS, which is most of the time
#
# ── FAIL-CLOSED ON CANNOT-TELL ──────────────────────────────────────────────
# An UNMARKED sandbox is not "safe to reap" — it is unattributable, which is the
# state twenty existing trees are in. It REFUSES, and the door is a DECLARATION
# rather than a flag:
#
#     DECLARE_REAP="the twenty .lens-1018-* trees are Design/Admin's round-five
#     and round-seven sandboxes, ruled reapable by #276; nothing holds them"
#       bash scripts/reap-lens-sandbox.sh .lens-1018-r5a
#
# ⚠️ THE HELD CHECK IS NEVER WAIVED, NOT EVEN BY A DECLARATION. A declaration is
# a claim about OWNERSHIP; it is not evidence about whether a process has the
# directory open this second, and no operator can know that by asserting it.
#
# ⚠️ AND LIVENESS IS KERNEL STATE, NEVER A COMMAND-LINE PATTERN. Canon records
# `pgrep -f` returning a false LIVE reading for three hours because the probe
# matched ITSELF. `/proc/*/cwd` and `lsof` answer about open handles and working
# directories; neither can match the asker's own argv.
# ============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED="$(git -C "$HERE" rev-parse --show-toplevel)"
DIR="${1:?usage: reap-lens-sandbox.sh <dir>}"
DIR="$(cd "$DIR" 2>/dev/null && pwd)" || {
  echo "🔴 $1 does not exist or is unreadable. Refusing — cannot tell." >&2; exit 1; }

case "$(basename "$DIR")" in
  .lens-*) : ;;
  *) echo "🔴 $DIR is not a lens sandbox (name must start with .lens-)." >&2; exit 1 ;;
esac
[ -d "$DIR/.lens-hooks" ] || { echo "🔴 $DIR carries no .lens-hooks — refusing." >&2; exit 1; }

# ── 1 · IS ANY PROCESS HOLDING THE TREE? ────────────────────────────────────
# ⚠️ THE PATTERN IS BUILT BY CONCATENATION so this script's own command line
# cannot satisfy it, and both controls run: a match that must be found, and a
# nonsense probe that must not.
lens_tree_held() {
  local dir="$1" hits=0 p tgt
  for p in /proc/[0-9]*; do
    tgt="$(readlink "$p/cwd" 2>/dev/null || true)"
    case "$tgt" in "$dir"|"$dir"/*) hits=$((hits + 1)) ;; esac
  done
  if command -v lsof >/dev/null 2>&1; then
    if lsof +D "$dir" >/dev/null 2>&1; then hits=$((hits + 1)); fi
  fi
  printf '%s' "$hits"
}

HELD="$(lens_tree_held "$DIR")"

# POSITIVE CONTROL — the probe must be capable of finding a holder at all.
# Without it a broken loop reports "nothing holds it" for every tree on the box.
# ⚠️ THE BACKGROUND JOB'S STDOUT IS REDIRECTED, AND THE FIRST VERSION HUNG ON
# EXACTLY THAT. Written as `_ctl="$( (cd … && sleep 5 & echo $!) )"`, the
# backgrounded `sleep` INHERITS the command substitution's stdout, so `$( … )`
# does not return until the pipe closes — five seconds later, with the control
# process already dead. The probe then found ZERO holders in a directory that had
# genuinely been held, and the control correctly refused the whole run.
#
# It failed SAFE and it failed LOUD, which is the only reason this is a footnote
# rather than a tree somebody lost: a control that reports "the probe is broken"
# is doing its job even when the thing that is broken is the control.
_ctl_dir="$(mktemp -d)"
( cd "$_ctl_dir" && exec sleep 5 ) >/dev/null 2>&1 &
_ctl=$!
sleep 0.4
_ctl_hits="$(lens_tree_held "$_ctl_dir")"
kill "$_ctl" 2>/dev/null || true
_nonsense="$(lens_tree_held "/proc/self/nonexistent-lens-control")"
if [ "$_ctl_hits" -lt 1 ] || [ "$_nonsense" -ne 0 ]; then
  rm -rf "$_ctl_dir" 2>/dev/null || true
  echo "🔴 the held-probe FAILED ITS OWN CONTROLS (found $_ctl_hits in a known-held dir," >&2
  echo "   $_nonsense in a nonexistent one). A probe that cannot find a holder reports" >&2
  echo "   'nothing holds it' for every tree on this box. Refusing — cannot tell." >&2
  exit 1
fi
rm -rf "$_ctl_dir" 2>/dev/null || true

if [ "$HELD" -gt 0 ]; then
  echo "🔴 REFUSING — $HELD process(es) hold $DIR right now."
  echo "   #213: the reaper refuses when the marker is FRESH **OR** when any"
  echo "   process holds the tree. This is the second arm, and no declaration"
  echo "   waives it — a declaration is a claim about OWNERSHIP, not evidence"
  echo "   about an open handle."
  exit 1
fi

# ── 2 · IS THE MARKER FRESH? ────────────────────────────────────────────────
MARKER="$DIR/.lens-marker"
if [ ! -r "$MARKER" ]; then
  if [ -n "${DECLARE_REAP:-}" ] && [ "${#DECLARE_REAP}" -ge 24 ]; then
    echo "⚠️  $DIR carries NO MARKER — unattributable."
    echo "   Proceeding on a DECLARATION, which is the record of why:"
    echo "     ${DECLARE_REAP}"
    echo "   (the held check above still ran, and passed — it is never waived.)"
  else
    echo "🔴 REFUSING — $DIR carries no .lens-marker, so it cannot be attributed."
    echo "   An unmarked sandbox is CANNOT-TELL about ownership, not 'safe'."
    echo "   It predates #206/#213, or its creator crashed before stamping one."
    echo
    echo "   The door is a DECLARATION of at least 24 characters, echoed to the"
    echo "   log, naming WHOSE it is and on what authority:"
    echo "     DECLARE_REAP=\"…\" bash scripts/reap-lens-sandbox.sh $DIR"
    exit 1
  fi
else
  _get() { sed -n "s/^$1=//p" "$MARKER" | head -1; }
  OWNER_SESSION="$(_get owner_session)"
  OWNER_PID="$(_get owner_pid)"
  OWNER_START="$(_get owner_starttime)"

  # ⚠️ OWNER-ALIVE IS pid AND START-TIME TOGETHER. A pid alone is reused; the
  # start tick cannot be inherited by a later process wearing the same number.
  ALIVE=no
  if [ -n "$OWNER_PID" ] && [ "$OWNER_PID" != "unknown" ] && [ -r "/proc/$OWNER_PID/stat" ]; then
    _now_start="$(awk '{print $22}' "/proc/$OWNER_PID/stat" 2>/dev/null || true)"
    if [ -n "$OWNER_START" ] && [ "$OWNER_START" != "unknown" ] && [ "$_now_start" = "$OWNER_START" ]; then
      ALIVE=yes
    fi
  fi

  # ⚠️ YOUR OWN TREE IS NOT SOMEBODY ELSE'S, AND THE FIRST BUILD OF THIS GUARD
  # REFUSED IT. #213 protects a tree whose owner is still working; the ORCHESTRATOR
  # reaping the sandboxes it created at close-out is the legitimate case the guard
  # exists to permit, and it is alive by definition while doing so.
  #
  #   A GUARD THAT REFUSES THE ONE ACTION IT WAS BUILT TO MAKE SAFE GETS
  #   WORKED AROUND, AND THEN IT PROTECTS NOTHING.
  #
  # Found by using it: the close-out sweep could not reap its own probe sandbox.
  # The held check above still ran and still applies — this exempts OWNERSHIP,
  # never occupancy.
  if [ "$ALIVE" = "yes" ] && [ -n "${CLAUDE_CODE_SESSION_ID:-}" ] \
     && [ "$OWNER_SESSION" = "$CLAUDE_CODE_SESSION_ID" ]; then
    echo "   marker      : this session's OWN sandbox (${OWNER_SESSION}) — reaping it is"
    echo "                 the close-out case, not the hazard. Nothing holds it."
    ALIVE=own
  fi

  if [ "$ALIVE" = "yes" ]; then
    echo "🔴 REFUSING — the owning session is STILL ALIVE, and it is not this one."
    echo "     owner     : ${OWNER_SESSION:-<unrecorded>}"
    echo "     this      : ${CLAUDE_CODE_SESSION_ID:-<unset>}"
    echo "     pid       : $OWNER_PID  (start-time $OWNER_START, still matching)"
    echo "   #213: refuse when the marker is FRESH. This tree is somebody else's."
    exit 1
  fi

  # ⚠️ AN UNPARSEABLE MARKER IS CANNOT-TELL, NOT ALL-CLEAR. A marker whose pid or
  # start-time is missing cannot answer the aliveness question at all, and a
  # guard that treats "I could not check" as "nobody is there" is the guard #206
  # was written to replace.
  if [ -z "$OWNER_PID" ] || [ "$OWNER_PID" = "unknown" ] || [ -z "$OWNER_START" ] || [ "$OWNER_START" = "unknown" ]; then
    if [ -n "${DECLARE_REAP:-}" ] && [ "${#DECLARE_REAP}" -ge 24 ]; then
      echo "⚠️  $DIR's marker cannot answer the aliveness question (pid/start-time"
      echo "    missing). Proceeding on a DECLARATION:"
      echo "      ${DECLARE_REAP}"
    else
      echo "🔴 REFUSING — $DIR's marker records no usable pid/start-time, so"
      echo "   whether its owner is alive CANNOT BE ESTABLISHED. Cannot-tell is"
      echo "   not all-clear."
      echo "   Override with a DECLARE_REAP of at least 24 characters."
      exit 1
    fi
  fi

  if [ "$ALIVE" = "own" ]; then
    echo "   marker      : session ${OWNER_SESSION:-<unrecorded>} — THIS session's own tree"
  else
    echo "   marker      : session ${OWNER_SESSION:-<unrecorded>}, owner pid $OWNER_PID — not alive"
  fi
  echo "   created     : $(_get created_utc)   ref: $(_get ref_under_test) @ $(_get ref_sha)"
fi

git -C "$SHARED" worktree remove --force "$DIR" 2>/dev/null || rm -rf "$DIR"
git -C "$SHARED" worktree prune
echo "🟢 reaped $DIR"
