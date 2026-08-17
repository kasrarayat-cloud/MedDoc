#!/usr/bin/env bash
# ============================================================================
# gh-runs.sh — the ONLY sanctioned door to "what ran on this SHA?".
#
# ⚠️ IT NO LONGER CALLS `gh run list`. Since F14-b (2026-08-17) the transport is
# `lib/runs-api.sh`, reached through `lib/inflight.sh`. `gh run list` calls the
# repo-wide `/actions/runs` route underneath, and that route 404'd for this
# repository for hours on 2026-08-17 while every other Actions route answered —
# blinding every waiter and every citation poll at once. The header below still
# describes `gh run list` because that is the history this file's refusals were
# built against, and every one of those refusals is still correct: the failure
# mode belongs to the QUESTION, not to the client that used to ask it.
# ----------------------------------------------------------------------------
# ⚠️ IT REFUSES ANY SHA UNDER 40 CHARACTERS, and that refusal is the whole
# product. `gh run list --commit <SHORT-sha>` returns **[]** for ANY
# abbreviation — exit 0, no warning, no "ambiguous" — and `?head_sha=<SHORT>`
# on the REST route matches nothing just as silently. A false all-clear that is
# indistinguishable from a quiet branch, whichever client asks.
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
       An abbreviated sha matches NOTHING on the runs routes — no error, no
       'ambiguous', just an empty result. That is a FALSE ALL-CLEAR.
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

WAIT_TIMEOUT="${GH_RUNS_WAIT_TIMEOUT:-3600}"
WAIT_INTERVAL="${GH_RUNS_WAIT_INTERVAL:-60}"
# How long "zero runs" is treated as PENDING rather than CANNOT-TELL.
WAIT_GRACE="${GH_RUNS_WAIT_GRACE:-180}"
total_seen=0

# ⚠️ THREE TERMINAL STATES, NOT TWO — AND THAT IS THE WHOLE FIX.
# This function used to collapse "some runs are still PENDING" and "a run has
# FAILED" into one exit code (1). A caller cannot tell them apart, so the
# canonical `until bash scripts/gh-runs.sh cited "$SHA"` loop polls FOREVER on a
# commit whose run has already concluded `failure` and can never reach 4 of 4.
#
# Measured 2026-08-17 on PR #705: `e2e` concluded FAILURE at 06:59Z
# (npm ECONNRESET in the image build). `cited` printed "3 of 4 success" and
# exited 1 — true, and indistinguishable from three-done-one-running. The waiter
# would have polled until the session ended.
#
# ⚠️ THIS IS THE SECOND TIME THIS SCRIPT COLLAPSED TWO STATES INTO ONE EXIT.
# The first was a fabricated sha vs a real sha with pending runs, fixed above by
# adding 2 = CANNOT TELL. Same author, same file, same shape — which is why the
# states are now enumerated in one place instead of being re-derived per branch.
#
#   0 = CITED       every run concluded success
#   1 = PENDING     at least one run not completed; no failures yet — retryable
#   2 = CANNOT TELL no runs, no such commit, broken instrument, timeout
#   3 = FAILED      a run concluded non-success — TERMINAL, will never cite
citation_state() {
  local rows="$1" sha="$2" total ok done_ failed
  total=$(echo "$rows"  | jq -r 'length')
  ok=$(echo "$rows"     | jq -r '[.[]|select(.conclusion=="success")]|length')
  done_=$(echo "$rows"  | jq -r '[.[]|select(.status=="completed")]|length')
  # A completed run whose conclusion is anything but success: failure,
  # cancelled, timed_out, startup_failure. All terminal for citation purposes.
  failed=$(echo "$rows" | jq -r '[.[]|select(.status=="completed" and .conclusion!="success")]|length')

  # ⚠️ A ZERO-RUN COMMIT IS NOT CITED. Without this, a sha nothing ever ran
  # against reports "all runs succeeded" — vacuously, which is the same
  # false all-clear one layer up.
  total_seen="$total"
  if [ "$total" -lt 1 ]; then
    echo "NOT CITED — no runs exist for $sha (vacuous, not clean)."
    return 2
  fi
  echo "$ok of $total success"
  if [ "$failed" -gt 0 ]; then
    echo "🔴 TERMINAL — $failed of $total concluded NON-SUCCESS. This sha can NEVER" >&2
    echo "   reach a full citation; waiting on it is an infinite loop. Re-run the" >&2
    echo "   failed job (and SAY WHY in the row — canon forbids re-run-and-hope)," >&2
    echo "   or push a fix. Offending runs:" >&2
    echo "$rows" | jq -r '.[]|select(.status=="completed" and .conclusion!="success")|"     \(.name): \(.conclusion)"' >&2
    return 3
  fi
  [ "$ok" -eq "$total" ] && return 0
  [ "$done_" -lt "$total" ] && return 1
  return 2
}

# Prove the runs API answers for this repo before believing any zero from it.
require_working_api() {
  inflight_require_gh || die2 "'gh' is not on PATH — CANNOT TELL, not an all-clear."
  inflight_positive_control || die2 "the runs API returned nothing for this repository — a zero from it proves nothing."
}

cmd="${1:-}"; sha="${2:-}"; opt="${3:-}"
# ⚠️ THE COMMAND IS VALIDATED BEFORE THE SHA, DELIBERATELY. Validating the sha
# first makes a wrong VERB report a sha complaint: `gh-runs.sh list --commit
# <sha>` (the shape muscle-memory reaches for) refused with "'--commit' is not
# hexadecimal", which is true, fail-closed, and names the wrong problem.
case "$cmd" in
  status|pending|cited|wait) ;;
  *) die2 "unknown command '${cmd:-}'. Use: status | pending | cited | wait <FULL-40-char-sha>
       This wrapper takes a BARE sha, never a \`--commit\` flag." ;;
esac

# ⚠️ `--force-fallback` IS A FLAG, NOT ONLY AN ENV VAR, AND THAT IS THE WHOLE
# REASON IT EXISTS HERE. `RUNS_API_FORCE_FALLBACK=1` already reaches the lib —
# but `VAR=1 bash …` and `env` are BOTH refused to the unattended loop, so an
# env-only hatch is inert for the one actor that runs every citation and every
# waiter. F14-a learned this on `check-citation.sh` and added the same flag;
# omitting it here would leave the fallback exercisable in exactly the sessions
# that never need to exercise it. **The path whose job is to work during an
# incident must be reachable when there is no incident.**
case "$opt" in
  ''|--force-fallback) ;;
  *) die2 "unknown option '$opt'. The only option is --force-fallback." ;;
esac
if [ "$opt" = "--force-fallback" ]; then
  export RUNS_API_FORCE_FALLBACK=1
  echo "   · --force-fallback: the repo-wide route is being REFUSED locally to" >&2
  echo "     exercise the per-workflow union. This is a drill, not an outage." >&2
fi

require_full_sha "$sha"
require_working_api

# ⚠️ THE TRANSPORT IS `lib/runs-api.sh` SINCE F14-b, NOT `gh run list`. `gh run
# list` calls the repo-wide `/actions/runs` route underneath, and that route
# 404'd for this repository for hours on 2026-08-17 while every other Actions
# route answered — so every waiter and every citation poll in the programme went
# blind at once. `fetch_rows` tries that route and, if it does not answer, unions
# the per-workflow route and asserts its own coverage against check-suites.
#
# ⚠️ THE ROW SHAPE IS UNCHANGED ON PURPOSE. `citation_state` and every jq
# expression below read `[{name,status,conclusion}]`, which is what `gh run list
# --json name,status,conclusion` produced. The payload is projected back to
# exactly that shape here, so the transport swap touches ONE function and the
# logic that reads it is not re-proved by hand.
#
# ⚠️ AND THIS ONE *IS* TRUNCATION-REFUSED, unlike inflight.sh's branch view. A
# single sha carries a handful of runs, so `total_count` and the fetched length
# must agree; if they do not, the answer is about a subset nobody chose. (The
# branch view cannot do this — `?branch=main` reports thousands against a
# 100-row page — which is why that limit is stated there rather than here.)
#
# ⚠️ IT SETS GLOBALS AND IS CALLED PLAINLY — NEVER AS `rows=$(fetch_rows)`.
# THE FIRST DRAFT DID EXACTLY THAT AND THE BANNER CAUGHT IT ON THE FIRST RUN:
# a command substitution is a SUBSHELL, so `ROWS_TRANSPORT` and `ROWS_BANNER`
# died with it and the banner printed *"transport: UNKNOWN — no _transport key"*
# over a verdict that was otherwise perfect (`4 of 4 success`, exit 0). That is
# the third sighting of this exact trap in this one library — `RUNS_API_MODE`,
# then `inflight_repo`'s tempting cache, then here — and the `*)` arm its author
# called "deliberate" is what discriminated. **A wrong provenance is worse than
# an absent one**, and nothing but that arm would have said so.
#
# ⚠️ AND THE SUBSHELL BROKE THE FAILURE PATH TOO, WHICH IS THE HALF NOBODY SEES.
# `die2` ends in `exit 2`; inside `$( )` that exits the SUBSHELL, so the script
# carried on with empty rows and died later under a different, wrong message.
# Called plainly, `die2` terminates the script with the reason it was given.
ROWS_TRANSPORT=""
ROWS_BANNER=""
rows=""
fetch_rows() {
  local payload total fetched
  payload="$(runs_api_for_sha "$REPO" "$sha" 100)" \
    || die2 "no runs transport answered for $sha."
  total="$(printf '%s' "$payload" | jq -r '.total_count // empty' 2>/dev/null)"
  fetched="$(printf '%s' "$payload" | jq -r '.workflow_runs | length' 2>/dev/null)"
  printf '%s' "$total" | grep -qE '^[0-9]+$' || die2 "the runs payload for $sha was not readable."
  [ "$total" = "$fetched" ] \
    || die2 "TRUNCATED — $total run(s) exist for $sha and $fetched were fetched.
       A verdict from a subset nobody chose is a cannot-tell, not an answer."
  ROWS_TRANSPORT="$(printf '%s' "$payload" | jq -r '._transport // "unknown"' 2>/dev/null)"
  ROWS_BANNER="$payload"
  rows="$(printf '%s' "$payload" | jq -c '[.workflow_runs[] | {name, status, conclusion}]')"
}

REPO="$(inflight_repo)" || die2 "cannot determine which repository this is."
fetch_rows
[ -n "$rows" ] || die2 "the runs query returned nothing readable for $sha."
# ⚠️ PRINTED, ALWAYS. A verdict whose PROVENANCE is unstated is how a fallback
# answer gets read as a normal one — the failure `runs_api_mode_banner`'s own
# header records being caught by a contradicting probe rather than by review.
runs_api_mode_banner "$ROWS_BANNER" >&2

case "$cmd" in
  status)
    echo "$rows" | jq -r '.[] | "  \(.name): \(.status) \(.conclusion // "")"'
    ;;
  pending)
    echo "$rows" | jq -r '[.[]|select(.status!="completed")]|length'
    ;;
  cited)
    citation_state "$rows" "$sha"; exit $?
    ;;
  wait)
    # ⚠️ THE POINT OF THIS SUBCOMMAND: `until … cited` CANNOT SEE A FAILURE.
    # `until` observes only zero/nonzero, so a FAILED run and a PENDING run are
    # the same signal to it and the loop never ends. The polling belongs HERE,
    # where the terminal states are distinguishable, instead of in every caller.
    deadline=$(( $(date +%s) + WAIT_TIMEOUT ))
    # ⚠️ PRINT ON CHANGE, NOT ON EVERY POLL. An hour's wait at 60s intervals is
    # 60 identical "3 of 4 success" lines, and for an UNATTENDED session the log
    # IS the report — noise there is not cosmetic, it buries the line that
    # matters. stderr is never suppressed: a TERMINAL block must always show.
    last=""; grace_said=0; grace_until=$(( $(date +%s) + WAIT_GRACE ))
    while :; do
      out=$(citation_state "$rows" "$sha"); st=$?
      # ⚠️ RESTORED. The grace-window edit below DELETED this line, silently, and
      # `wait` then succeeded in total silence — no "4 of 4 success", nothing. The
      # anchor matched, the file parsed, and the grace tests passed because they
      # asserted the NEW behaviour and never re-asserted the PRESERVED behaviour.
      # A scripted edit proves its own application; it must also prove it did not
      # remove what it was not asked to remove.
      if [ "$out" != "$last" ]; then printf '%s\n' "$out"; last="$out"; fi
      # ⚠️ COUNTED HERE, NOT INSIDE citation_state. That function runs in a
      # COMMAND SUBSTITUTION, so anything it assigns dies with the subshell — the
      # first version read a `total_seen` global that was therefore ALWAYS 0, and
      # the guard below would have fired for ANY cannot-tell, masking a broken
      # instrument as "runs haven't appeared yet". Exactly what the bound exists
      # to prevent.
      seen=$(echo "$rows" | jq -r 'length' 2>/dev/null || echo 0)
      # ⚠️ THE POST-PUSH GRACE WINDOW. Immediately after a push GitHub has not
      # created the runs yet, so `citation_state` correctly reports 2 = CANNOT
      # TELL on zero rows. Returning that instantly makes `wait` useless for its
      # PRIMARY job — waiting on a citation for the push you just made.
      #
      # ⚠️ AND IT IS BOUNDED ON PURPOSE. "No runs yet" and "this commit will
      # NEVER have runs" are genuinely indistinguishable from outside, and
      # conflating them is the exact class this file was just fixed for. So the
      # grace period EXPIRES and the answer reverts to 2 — honest, not hopeful.
      # Measured 2026-08-17: a PR head sat at zero runs for >3 minutes and the
      # cause was not propagation at all, it was a CONFLICTING PR, which gets no
      # merge ref to run against. A grace window must not hide that.
      if [ "$st" -eq 2 ] && [ "${seen:-0}" -eq 0 ] && [ "$(date +%s)" -lt "$grace_until" ]; then
        st=1
        # ⚠️ ITS OWN FLAG, NOT `last`. The print-on-change line above also writes
        # `last`, so sharing it made each side clobber the other and the grace
        # notice printed once per poll — the exact noise this loop was fixed for,
        # reintroduced by two mechanisms owning one variable.
        [ "$grace_said" = "0" ] && { echo "no runs yet — waiting up to ${WAIT_GRACE}s for them to appear"; grace_said=1; }
      fi
      [ "$st" -eq 1 ] || exit "$st"          # 0 cited · 3 failed · 2 cannot tell
      if [ "$(date +%s)" -ge "$deadline" ]; then
        die2 "TIMED OUT after ${WAIT_TIMEOUT}s waiting on $sha — still pending.
       This is a CANNOT-TELL, not a failure: the runs may yet finish."
      fi
      sleep "$WAIT_INTERVAL"
      # ⚠️ THE SAME DOOR AS THE FIRST FETCH, DELIBERATELY. An earlier shape had
      # the initial read and the mid-wait re-read as two separate `gh run list`
      # calls, so a transport change had to be made in two places and the second
      # one is the one that gets forgotten. One function, two callers.
      prev_transport="$ROWS_TRANSPORT"
      fetch_rows
      # ⚠️ A TRANSPORT THAT CHANGES MID-WAIT IS REPORTED, NOT AVERAGED. An
      # outage that starts or ends underneath a poll is exactly the
      # intermittency the debounce rule exists for: a waiter that only prints
      # its final verdict cannot be audited.
      if [ "$ROWS_TRANSPORT" != "$prev_transport" ]; then
        echo "   · ⚠️ transport changed mid-wait: $prev_transport → $ROWS_TRANSPORT" >&2
        runs_api_mode_banner "$ROWS_BANNER" >&2
      fi
    done
    ;;
  *)
    die2 "unknown command '${cmd:-}'. Use: status | pending | cited"
    ;;
esac
