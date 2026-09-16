#!/usr/bin/env bash
# ============================================================================
# run_watched — run a command, stream its output live, and REFUSE to wait
# forever on a child that finished its work and never exited — WITHOUT ever
# killing a command that is merely busy and quiet.
#
#   run_watched [--in-cid <CID> --sig <cmdline-substring>] -- <cmd...>
#   → streams combined stdout+stderr live to this terminal
#   → sets the global RUN_RC to the child's real exit code
#   → on a timeout: kills the child, sets RUN_RC=124, prints WHY (never silent)
#
# ── WHY THIS EXISTS — 2026-09-15, the RULING C colon-note ruled act ──────────
# A certify script printed its whole transcript through "[323] DONE" at
# 20:12:19Z and then HUNG, held alive by an open pg pool handle, because its
# success path never called process.exit(). The door — a bare `docker exec`
# in run-ruled-mutation.sh — blocked on it in SILENCE for 5h24m. The act had
# FULLY LANDED; nothing said so and nothing timed out.
#
# Two failures, fixed in two layers:
#   · the SCRIPT should exit explicitly on success  → scripts/lib/exit-cleanly.ts
#   · the DOOR should not wait in silence forever    → THIS FILE
#
# ── THE HARD PART: "finished + hung" LOOKS EXACTLY LIKE "busy + quiet" ────────
# Output silence alone cannot tell the 2026-09-15 shape (work done, process
# lingering) from a legitimate long quiet stretch — a single Anthropic model
# call on the certify path can be silent for up to the SDK's 600s-per-attempt
# timeout (× retries), and a big backfill UPDATE emits nothing until it commits.
# Killing on silence alone would SIGKILL a healthy in-flight irreversible act
# and roll its transaction back. So:
#
#   · the CEILING (wall-clock, RULED_ACT_MAX_SECS) is the always-on backstop.
#     It bounds ANY hang and is generous enough to clear any real act. It is
#     NEVER disabled — 0/empty/invalid coerce to the default, not to "off".
#   · the IDLE detector only FAST-KILLS after it has seen an explicit COMPLETION
#     SENTINEL in the output (printed by exitCleanly / runCli). Without that
#     signal a quiet stretch is NOT a hang we may kill — the detector prints a
#     heartbeat (so it is never a silent wait) and leaves the kill to the
#     ceiling. A script that never signals completion is bounded, not murdered.
#
# ── KILLING THE RIGHT THING, SAFELY ──────────────────────────────────────────
# `timeout` runs the command in its own process group and reaps that group. For
# a `docker exec` target the in-container process is in another namespace and
# `docker exec` does not forward signals, so the caller passes --in-cid/--sig
# and we `docker exec <CID> pkill -TERM -f <sig>`. TWO hazards the adversarial
# pass found and this file now handles:
#   · `pkill -f` treats its argument as a REGEX — an unescaped cmdline can
#     over-match (`||` → every process, killing the live worker), under-match
#     (`$` anchor → nothing reaped while the act runs), or error (`[`). We
#     ERE-ESCAPE the signature to a literal before every pkill/pgrep.
#   · a wedged docker daemon makes `docker exec` block forever — so every reap
#     `docker exec` is itself wrapped in `timeout`, or the watchdog becomes the
#     new silent wait.
#
# ⚠️ KNOWN LIMITATION (accepted): two DIFFERENT ruled acts running the SAME
# script in the SAME container within the window share a signature, so one act's
# reap can signal the other's process. Ruled acts are serialized by an operator
# and the door already refuses more than one target container; a second
# same-script act in one container is out of scope. Documented, not guarded.
#
# ── TUNING (env; 0/empty/invalid → the default, never "disabled") ────────────
#   RULED_ACT_IDLE_SECS  no-output-while-alive before a heartbeat / sentinel
#                        fast-kill                                       [1800]
#   RULED_ACT_MAX_SECS   absolute wall-clock ceiling (never disabled)    [3600]
#   RULED_ACT_POLL       sample interval, seconds                           [5]
#   RULED_ACT_SENTINEL   the completion line exitCleanly prints
#                                                        [__RULED_ACT_COMPLETE__]
# ============================================================================

# The completion sentinel. ⚠️ ONE RULE, TWO READERS: this literal MUST equal the
# one printed by apps/transcribe-md/scripts/lib/exit-cleanly.ts. The gate
# `gate-ruled-act-exit-and-watchdog.test.ts` asserts both files carry it so they
# cannot drift.
RUN_WATCHED_SENTINEL_DEFAULT='__RULED_ACT_COMPLETE__'

# Coerce a value to a positive base-10 integer, else the given default. Empty,
# non-numeric, and ANY numeric zero (0, 00, 000, …) fall to the default — a
# ceiling can be RAISED but never switched off, so `RULED_ACT_MAX_SECS=0` (or
# `00`) cannot reintroduce the silent wait. The result is normalized to plain
# base-10 (leading zeros stripped) so downstream `timeout`/`sleep`/$((…)) agree
# and a value like `010` is 10 everywhere, not octal-8 in arithmetic.
_watch_int() {
  # LC_ALL=C so the [!0-9] glob is byte-wise — a multibyte digit (e.g. Arabic
  # ٦٠) is then non-[0-9] and falls to the default rather than erroring $((…)).
  local LC_ALL=C v="${1:-}" n
  case "$v" in
    '' | *[!0-9]*) printf '%s' "$2"; return ;;
  esac
  n=$((10#$v)) 2>/dev/null || n=""
  if [ -z "$n" ] || ! [ "$n" -ge 1 ] 2>/dev/null; then
    printf '%s' "$2"
  else
    printf '%s' "$n"
  fi
}

# ERE-escape a string so `pkill -f` / `pgrep -f` match it LITERALLY, not as a
# regex. Escapes \ . ^ $ * + ? ( ) [ ] { } | so a cmdline containing shell
# operators cannot over-match, under-match, or error.
_ere_escape() {
  printf '%s' "$1" | sed 's/[]\\[(){}.^$*+?|]/\\&/g'
}

run_watched() {
  local in_cid="" sig=""
  local -a cmd=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --in-cid) in_cid="${2:-}"; shift 2 ;;
      --sig)    sig="${2:-}";    shift 2 ;;
      --)       shift; cmd=("$@"); break ;;
      *)        cmd=("$@"); break ;;
    esac
  done
  if [ "${#cmd[@]}" -eq 0 ]; then
    echo "run_watched: no command given" >&2
    RUN_RC=2
    return 0
  fi

  local idle_limit max poll sentinel
  idle_limit="$(_watch_int "${RULED_ACT_IDLE_SECS:-}" 1800)"
  max="$(_watch_int "${RULED_ACT_MAX_SECS:-}" 3600)"
  poll="$(_watch_int "${RULED_ACT_POLL:-}" 5)"
  sentinel="${RULED_ACT_SENTINEL:-$RUN_WATCHED_SENTINEL_DEFAULT}"

  local esig=""
  [ -n "$sig" ] && esig="$(_ere_escape "$sig")"

  local reap_to
  reap_to="$(_watch_int "${RULED_ACT_REAP_SECS:-}" 15)"

  # Reap the in-container process tree, time-bounded so a wedged daemon cannot
  # make the reaper itself the new hang. $1 = signal (TERM/KILL).
  _reap_incontainer() {
    [ -n "$in_cid" ] && [ -n "$esig" ] || return 0
    timeout "$reap_to" docker exec "$in_cid" pkill "-$1" -f "$esig" 2>/dev/null
  }

  local logf
  logf="$(mktemp)"

  # `timeout` gives a correct process-group reap and the (never-disabled)
  # ceiling. Idle detection is layered on top by sampling the log's growth.
  timeout -k 15 "$max" "${cmd[@]}" >"$logf" 2>&1 &
  local top=$!

  tail -n +1 -f --pid="$top" "$logf" 2>/dev/null &
  local tailpid=$!

  local last=-1 idle=0 warned_at=0 sentinel_seen=0 finished=""
  while kill -0 "$top" 2>/dev/null; do
    sleep "$poll"
    local size
    size="$(stat -c%s "$logf" 2>/dev/null || echo 0)"
    if [ "$size" = "$last" ]; then
      idle=$((idle + poll))
    else
      idle=0
      last="$size"
    fi
    if [ "$sentinel_seen" -eq 0 ] && grep -Fq "$sentinel" "$logf" 2>/dev/null; then
      sentinel_seen=1
    fi
    if [ "$idle" -ge "$idle_limit" ]; then
      if [ "$sentinel_seen" -eq 1 ]; then
        # The script announced completion and then stopped emitting while still
        # alive — the 2026-09-15 shape, now positively identified. Safe to kill.
        finished="yes"
        break
      fi
      # No completion signal. This may be a healthy, busy, quiet act (a slow
      # model call, a long UPDATE) — we must NOT kill it. Break the silence with
      # a heartbeat and let the ceiling be the authority.
      if [ $((idle - warned_at)) -ge "$idle_limit" ]; then
        echo "⏱️  WATCHDOG — no output for ${idle}s and no completion signal yet."
        echo "    NOT killing: a quiet stretch is not proof of a hang (a slow"
        echo "    model call or a long UPDATE looks identical). The ${max}s"
        echo "    ceiling is the backstop; still $((max - idle))s from it."
        warned_at="$idle"
      fi
    fi
  done

  sleep 1
  kill "$tailpid" 2>/dev/null
  wait "$tailpid" 2>/dev/null

  if [ -n "$finished" ]; then
    echo "═══════════════════════════════════════════════════════════════════"
    echo "⏱️  WATCHDOG — the command SIGNALLED COMPLETION BUT DID NOT EXIT."
    echo "    It printed the completion sentinel and then went quiet for"
    echo "    ${idle_limit}s while still alive — the 2026-09-15 shape. The work"
    echo "    reached the script's own end; an explicit exit is missing or"
    echo "    stalled. The act LIKELY landed, but the door did not decide that —"
    echo "    JUDGE the declaration, every row, before re-running."
    _reap_incontainer TERM
    kill -TERM "$top" 2>/dev/null
    local g
    for g in 1 2 3 4 5; do
      kill -0 "$top" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$top" 2>/dev/null; then
      kill -KILL "$top" 2>/dev/null
      _reap_incontainer KILL
    fi
    wait "$top" 2>/dev/null
    echo "═══════════════════════════════════════════════════════════════════"
    RUN_RC=124
  else
    wait "$top"
    RUN_RC=$?
    # `timeout` returns 124 when IT fired the ceiling. The command was killed
    # WITHOUT signalling completion — it may have been mid-work, so the act may
    # be PARTIAL or not landed. Say so, on host and in-container alike, and reap
    # the in-container process (timeout's group reap does not reach it).
    if [ "$RUN_RC" -eq 124 ]; then
      echo "═══════════════════════════════════════════════════════════════════"
      echo "⏱️  WATCHDOG — WALL-CLOCK CEILING ${max}s REACHED; command killed."
      echo "    It never signalled completion, so it may have been MID-WORK: the"
      echo "    act may be PARTIAL or not landed. Do NOT assume it finished —"
      echo "    JUDGE the declaration, every row, before re-running."
      if [ -n "$in_cid" ] && [ -n "$esig" ]; then
        echo "    reaping in-container: docker exec ${in_cid:0:12} pkill -TERM -f <sig>"
        _reap_incontainer TERM
        local k
        for k in 1 2 3 4 5; do
          timeout "$reap_to" docker exec "$in_cid" pgrep -f "$esig" >/dev/null 2>&1 || break
          sleep 1
        done
        _reap_incontainer KILL
      fi
      echo "═══════════════════════════════════════════════════════════════════"
    fi
  fi

  rm -f "$logf"
  return 0
}
