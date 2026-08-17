#!/usr/bin/env bash
# ============================================================================
# runs-api.sh — the ONE transport for "what ran on this SHA / this branch?".
#
# SOURCED BY, AND VERIFIED BY GREP RATHER THAN ASSERTED — F14-b, 2026-08-17:
#
#     check-citation.sh          directly          — the CITATION door
#     lib/inflight.sh            directly          — and therefore:
#       · scripts/hooks/pre-push (sources inflight.sh)   — the PUSH door
#       · scripts/merge-pr.sh    (sources inflight.sh)   — the MERGE door
#       · scripts/gh-runs.sh     (sources inflight.sh)   — waiters and polls
#
# ⚠️ THIS BLOCK HAS BEEN WRONG IN BOTH DIRECTIONS AND THAT IS WHY IT IS A LIST.
# It first read *"Sourced by check-citation.sh, gh-runs.sh and lib/inflight.sh"*
# in the present tense while only ONE of the three was wired — the
# `DEPLOYMENT_RUNBOOK.md §5.6` shape, a wish written as a fact, which a reader
# takes as a description of the running system. F14-a corrected it to a scope
# note; F14-b makes the original sentence true. **If you edit the wiring, edit
# this list in the same commit and check it with a grep, not with memory:**
#
#     grep -rln 'runs-api\.sh' scripts/
#
# ⚠️ ALL THREE DOORS ARE COVERED; THE HONEST LIMIT IS NOW ELSEWHERE. It is the
# BRANCH view's missing coverage control — see `runs_api_for_branch` — where a
# fallback-mode count is a FLOOR rather than a measurement. That limit is
# surfaced by every caller instead of being papered over.
#
# Never copied — one implementation, however many callers.
# ----------------------------------------------------------------------------
# ⚠️ WHY THIS FILE EXISTS AT ALL — a measured outage, not a hypothetical.
#
# On 2026-08-17 GitHub's REPO-WIDE workflow-runs route began returning 404 for
# this repository, and stayed down for hours. Isolated at 13:38Z:
#
#     GET /repos/{o}/{r}                                    200
#     GET /repos/{o}/{r}/actions/workflows                  200  (7 workflows)
#     GET /repos/{o}/{r}/actions/runs                       404   <-- and with
#     GET /repos/{o}/{r}/actions/runs?per_page=1            404        ANY
#     GET /repos/{o}/{r}/actions/runs?head_sha=<full-sha>   404        params
#     GET /repos/{o}/{r}/actions/workflows/{id}/runs        200
#
# Every citation and in-flight instrument in this repo funnelled through the one
# route that was down — `check-citation.sh` via `gh api …/actions/runs`, and
# `gh-runs.sh` + `lib/inflight.sh` via `gh run list`, which calls it underneath.
# So the whole programme's gate had a SINGLE POINT OF FAILURE, and when it
# failed nothing could be cited, pushed or merged. Session 03 parked PR #710 on
# exactly this.
#
# ⚠️ THE INSTRUMENTS BEHAVED CORRECTLY. They refused, fail-closed, loudly, and
# neither was routed around. That is the good half and it is not what is being
# fixed. What is being fixed is that a correct refusal is still a stopped queue.
#
# ── THE TRANSPORTS, AND WHY THE FALLBACK IS NOT A WORKAROUND ───────────────
#
#   PRIMARY  : /actions/runs?<filter>                 — one call, the normal path
#   FALLBACK : /actions/workflows/{id}/runs?<filter>  — one call per workflow,
#                                                       unioned
#
# The fallback returns the SAME run objects with the SAME fields; it is a
# different index over one table, not a different measurement. It is arguably
# the more precise question — it enumerates BY WORKFLOW rather than trusting a
# flat list to contain everything — and that is what makes the coverage control
# below possible at all.
#
# ── THREE THINGS THE FALLBACK MUST NOT QUIETLY BREAK ───────────────────────
#
# (1) THE RECONCILIATION ARM MUST STAY FALSIFIABLE. check-citation.sh asserts
#     `sum(buckets) == total_count`, which only means something because
#     `total_count` comes from the SERVER and the buckets come from counting
#     rows. If the fallback computed `total_count` by counting the rows it had
#     just merged, the two sides would be the same number by construction and
#     the arm would agree forever. So TOTAL is the SUM OF THE SERVER-REPORTED
#     `total_count` OF EACH PER-WORKFLOW QUERY, never a length. A per-workflow
#     query that truncates then makes SUM < TOTAL — which is exactly the
#     cannot-tell the arm exists to raise.
#
# (2) EVERY WORKFLOW IS QUERIED, NOT ONLY THE FOUR REQUIRED ONES. Querying just
#     the required set would silently empty check-citation.sh's `extra` bucket
#     and make (1) vacuous. The universe stays the repository's whole workflow
#     list.
#
# (3) ⚠️ THE FALLBACK'S OWN COVERAGE IS ASSERTED, NOT ASSUMED — see below.
#
# ── THE COVERAGE CONTROL, AND IT IS THE LOAD-BEARING PART ──────────────────
#
# The fallback can only see runs of workflows that `/actions/workflows` still
# lists. A workflow whose file was deleted, or one the enumeration missed for
# any reason, has runs the union will never fetch — and it would be INVISIBLE,
# because (1) reconciles the union against itself.
#
# So a THIRD, INDEPENDENT route is used as a control:
#
#     GET /repos/{o}/{r}/commits/{sha}/check-suites
#
# GitHub opens one check suite per workflow run, and this route is indexed by
# COMMIT rather than by workflow — so it cannot inherit the enumeration's blind
# spot. If the count of `github-actions` check suites on the SHA does not equal
# the union's total, the union is missing something and the answer is CANNOT
# TELL, never a citation.
#
# MEASURED 2026-08-17, 14 consecutive `main` commits: union == suites on 14 of
# 14 (including a 12-run merge and a 0-run commit).
# MUTATION-PROVED, because a control nobody can make fail is decoration —
# dropping ONE workflow (`e2e`) from the enumeration:
#
#     4-run commit    suites= 4  union= 4 AGREE   union(minus e2e)= 3 DIVERGE ✔
#     12-run commit   suites=12  union=12 AGREE   union(minus e2e)=11 DIVERGE ✔
#     0-run commit    suites= 0  union= 0 AGREE   union(minus e2e)= 0 AGREE   ✘
#
# ⚠️ RE-PROVED INDEPENDENTLY 2026-08-17 BY THE SESSION THAT LANDED THIS, AND THE
# SECOND MUTATION IS THE ONE THAT MATTERS. Dropping `e2e` proves the control
# DETECTS incompleteness — but `e2e` is a REQUIRED workflow, so its absence
# would have made the citation go RED (3 of 4) anyway. That is not the failure
# worth guarding.
#
# So the mutation was re-aimed at a NON-REQUIRED workflow, where the union still
# contains all four required runs and the citation therefore goes GREEN over an
# incomplete universe — the false green, which nothing else would catch:
#
#     drop `Dependabot Updates`   union= 4  suites=12  DIVERGE ✔  -> cannot tell
#
# Without the control that run cites 4 of 4 and looks perfect. WITH it, the
# verdict is withheld. `1b1de497…`, both mutations asserted applied before their
# results were read, and the file restored from a scratch copy rather than git.
#
# ⚠️ HONEST LIMIT, STATED SO THE CONTROL IS NOT READ WIDER THAN IT IS: the third
# row is a VACUOUS agreement. On a commit with zero runs the control cannot
# discriminate, because there is nothing to be missing. That is not load-bearing
# here — check-citation.sh routes zero-runs into its own branch, which is a
# FINDING or a cannot-tell and never a green citation — but it is the shape to
# remember if this lib is ever reused somewhere that treats zero as a pass.
#
# ⚠️ AND THE CONTROL IS PER-COMMIT ONLY. check-suites is indexed by commit, so
# there is no equivalent for the BRANCH view. `runs_api_for_branch` therefore
# runs UNCONTROLLED in fallback mode and says so via the payload's `_control`
# key, which `runs_api_mode_banner` prints. (This sentence named the dead global
# `RUNS_API_CONTROL_NOTE` until 2026-08-17 — the same half-landed rename the
# banner itself carried.) The
# branch view's job is to answer "is anything in flight on this ref", where the
# failure that matters is under-reporting a pending run; a missing workflow
# makes it under-report, so callers treat fallback-mode branch counts as a
# floor. Named rather than papered over.
#
# ── EXIT CONVENTION ────────────────────────────────────────────────────────
#   0 = answered.  1 = CANNOT TELL. There is deliberately no third code: every
#   caller here already refuses on cannot-tell, and a lib that could say
#   "probably fine" would be the loosening this file exists to avoid.
#
# ⚠️ NOTHING HERE EVER RETURNS AN EMPTY RESULT TO MEAN "the API is unwell". A
# broken query and a quiet commit produce the same zero — this repo's most
# expensive recurring lesson — so a transport failure is rc 1, always.
# ============================================================================

# ⚠️ THE TRANSPORT IS REPORTED IN THE PAYLOAD, NOT IN A GLOBAL — AND THAT COST A
# ROUND. The first draft set `RUNS_API_MODE` inside the query functions and had
# callers read it afterwards. Every caller invokes them as `X="$(runs_api_…)"`,
# which is a COMMAND SUBSTITUTION, which is a SUBSHELL — so the assignment was
# discarded and the caller read a stale empty value. The banner printed
# "transport: repo-wide /actions/runs" for a citation the fallback had just
# produced, WHILE the repo-wide route was 404ing in the same minute.
#
# ⚠️ THE VERDICT WAS RIGHT AND THE PROVENANCE WAS A LIE, which is the worse half:
# nothing was wrong with the citation, so nothing would ever have prompted a
# re-check. It was caught only because the banner contradicted a `gh api` probe
# run seconds later — this repo's own "two readings with opposite meanings is ONE
# broken instrument" tell, fired on its author.
#
# So the answer travels with the data: `_transport` and `_control` are keys ON
# the emitted object. A value that must cross a subshell boundary cannot be a
# global, and "it worked when I tested the function directly" is exactly how this
# survives review.
# cached enumeration, per process (read-only use, safe).
# ⚠️ `:=` NOT `=`, SINCE F14-b. This file is now sourced from TWO places that can
# both be live at once — `check-citation.sh` directly, and `lib/inflight.sh`
# (hence `gh-runs.sh`, `merge-pr.sh` and the pre-push hook). A bare `=` would
# reset the cache on the second source, turning one workflow enumeration into
# two identical API calls. Harmless, and wrong for a file whose whole subject is
# behaving well while an API is unwell.
: "${RUNS_API_WORKFLOW_IDS:=}"

runs_api_require() {
  command -v gh >/dev/null 2>&1 || {
    echo "CANNOT TELL — 'gh' is not on PATH." >&2; return 1; }
  command -v jq >/dev/null 2>&1 || {
    echo "CANNOT TELL — 'jq' is not on PATH; runs-api.sh cannot parse a response." >&2; return 1; }
  return 0
}

# _runs_api_raw <path> -> body on stdout; rc 0 ok, 1 any failure (cannot tell).
_runs_api_raw() {
  local out
  out="$(gh api "$1" 2>/dev/null)" || return 1
  [ -n "$out" ] || return 1
  printf '%s' "$out"
}

# _runs_api_repo_wide <path> — the PRIMARY transport, behind one testability
# hook. Identical to _runs_api_raw except that it can be told to refuse.
#
# ⚠️ `RUNS_API_FORCE_FALLBACK=1` MAKES IT REFUSE, AND THAT EXISTS SO THE
# FALLBACK CAN BE EXERCISED WITHOUT WAITING FOR AN OUTAGE. As first written,
# the per-workflow path was reachable ONLY while GitHub's repo-wide route was
# down — so the one code path whose entire job is to work during an incident
# was the one path no test could ever enter. It would have been verified for
# the first time by the next outage, which is the worst possible moment to
# discover a typo.
#
# ⚠️ IT GATES THE REPO-WIDE ROUTE ONLY. The per-workflow and check-suites
# routes still go through _runs_api_raw directly, because forcing THOSE to fail
# would not simulate an outage — it would simulate a broken fallback, which is
# a different experiment and would make the union un-runnable.
_runs_api_repo_wide() {
  [ "${RUNS_API_FORCE_FALLBACK:-}" = "1" ] && return 1
  _runs_api_raw "$1"
}

# _runs_api_workflow_ids <repo> -> ids, one per line. Cached.
_runs_api_workflow_ids() {
  local repo="$1" body
  if [ -n "$RUNS_API_WORKFLOW_IDS" ]; then printf '%s\n' "$RUNS_API_WORKFLOW_IDS"; return 0; fi
  body="$(_runs_api_raw "repos/$repo/actions/workflows?per_page=100")" || return 1
  # ⚠️ Truncation here would silently narrow the universe, which is precisely
  # the failure the coverage control exists to catch — but catching it late is
  # worse than refusing early, so it is refused here too.
  local tc len
  tc="$(printf '%s' "$body" | jq -r '.total_count // 0')"
  len="$(printf '%s' "$body" | jq -r '.workflows | length')"
  [ "$tc" = "$len" ] || { echo "CANNOT TELL — $tc workflows exist, $len fetched." >&2; return 1; }
  [ "$len" -gt 0 ] || { echo "CANNOT TELL — this repository reports zero workflows." >&2; return 1; }
  RUNS_API_WORKFLOW_IDS="$(printf '%s' "$body" | jq -r '.workflows[].id')"
  printf '%s\n' "$RUNS_API_WORKFLOW_IDS"
}

# _runs_api_union <repo> <key> <value> <per_page>
# stdout: {"total_count":N,"workflow_runs":[…]} with N summed from the SERVER's
# per-query total_count — see (1) in the header.
_runs_api_union() {
  local repo="$1" key="$2" val="$3" pp="$4"
  local wids w body total=0 acc="" n
  wids="$(_runs_api_workflow_ids "$repo")" || return 1
  while read -r w; do
    [ -n "$w" ] || continue
    body="$(_runs_api_raw "repos/$repo/actions/workflows/$w/runs?$key=$val&per_page=$pp")" || return 1
    n="$(printf '%s' "$body" | jq -r '.total_count // empty')"
    printf '%s' "$n" | grep -qE '^[0-9]+$' || return 1
    total=$(( total + n ))
    acc="${acc}$(printf '%s' "$body" | jq -c '.workflow_runs')"$'\n'
  done <<< "$wids"
  printf '%s' "$acc" | jq -s --argjson t "$total" '{total_count:$t, workflow_runs:(add // [])}'
}

# _runs_api_coverage <repo> <sha> <union_total>
#   0 = control agrees   1 = DIVERGED (union is missing runs)   2 = cannot run it
_runs_api_coverage() {
  local repo="$1" sha="$2" total="$3" body tc n
  body="$(_runs_api_raw "repos/$repo/commits/$sha/check-suites?per_page=100")" || return 2
  tc="$(printf '%s' "$body" | jq -r '.total_count // empty')"
  n="$(printf '%s' "$body" | jq -r '[.check_suites[]|select(.app.slug=="github-actions")]|length')"
  printf '%s' "$tc" | grep -qE '^[0-9]+$' || return 2
  # Truncated control = no control. Not an accusation either way.
  [ "$tc" -le 100 ] || return 2
  [ "$n" = "$total" ] && return 0
  echo "COVERAGE CONTROL DIVERGED — $total run(s) found by union, but $n github-actions" >&2
  echo "  check suite(s) exist on $sha. The per-workflow enumeration is missing runs," >&2
  echo "  so any verdict from it would be about a subset nobody chose." >&2
  return 1
}

# ── PUBLIC ────────────────────────────────────────────────────────────────

# runs_api_control <repo> -> a non-zero total on stdout; rc 0 ok, 1 cannot tell.
# The positive control: prove the transport answers for THIS repo before any
# zero from it is believed.
runs_api_control() {
  local repo="$1" body n wids w tot=0
  runs_api_require || return 1
  if body="$(_runs_api_repo_wide "repos/$repo/actions/runs?per_page=1")"; then
    n="$(printf '%s' "$body" | jq -r '.total_count // empty')"
    if printf '%s' "$n" | grep -qE '^[0-9]+$' && [ "$n" -gt 0 ]; then
      printf '%s' "$n"; return 0
    fi
  fi
  wids="$(_runs_api_workflow_ids "$repo")" || return 1
  while read -r w; do
    [ -n "$w" ] || continue
    body="$(_runs_api_raw "repos/$repo/actions/workflows/$w/runs?per_page=1")" || return 1
    n="$(printf '%s' "$body" | jq -r '.total_count // 0')"
    printf '%s' "$n" | grep -qE '^[0-9]+$' && tot=$(( tot + n ))
  done <<< "$wids"
  [ "$tot" -gt 0 ] || { echo "CANNOT TELL — neither transport reports any run for $repo." >&2; return 1; }
  printf '%s' "$tot"; return 0
}

# runs_api_for_sha <repo> <sha> [per_page]
# stdout: {"total_count":N,"workflow_runs":[…]}; rc 0 ok, 1 cannot tell.
runs_api_for_sha() {
  local repo="$1" sha="$2" pp="${3:-100}" body total rc note
  runs_api_require || return 1
  if body="$(_runs_api_repo_wide "repos/$repo/actions/runs?head_sha=$sha&per_page=$pp")"; then
    printf '%s' "$body" | jq -c '. + {_transport:"repo-wide", _control:""}'; return 0
  fi
  body="$(_runs_api_union "$repo" head_sha "$sha" "$pp")" || {
    echo "CANNOT TELL — neither the repo-wide nor the per-workflow route answered for $sha." >&2
    return 1; }
  total="$(printf '%s' "$body" | jq -r '.total_count')"
  _runs_api_coverage "$repo" "$sha" "$total"; rc=$?
  case $rc in
    0) note="coverage control: $total run(s) = $total github-actions check suite(s) — the union is complete" ;;
    1) return 1 ;;
    2) note="⚠️ coverage control UNAVAILABLE (check-suites did not answer or was truncated) — the union is unverified" ;;
  esac
  printf '%s' "$body" | jq -c --arg n "$note" '. + {_transport:"per-workflow", _control:$n}'
}

# runs_api_for_branch <repo> <branch> [per_page]
# ⚠️ NO coverage control exists for a branch — see the header. In fallback mode
# the count is a FLOOR, and the payload's `_control` key says so; callers surface
# it (`runs_api_mode_banner`, and `inflight.sh`'s INFLIGHT_NOTE).
#
# ⚠️ THIS COMMENT NAMED THE DEAD GLOBAL `RUNS_API_CONTROL_NOTE` UNTIL F14-b —
# the same half-landed rename the banner itself carried, surviving in the one
# place `set -u` cannot reach. A comment naming a variable nothing assigns is
# how the next reader reintroduces it.
runs_api_for_branch() {
  local repo="$1" br="$2" pp="${3:-100}" body
  runs_api_require || return 1
  if body="$(_runs_api_repo_wide "repos/$repo/actions/runs?branch=$br&per_page=$pp")"; then
    printf '%s' "$body" | jq -c '. + {_transport:"repo-wide", _control:""}'; return 0
  fi
  body="$(_runs_api_union "$repo" branch "$br" "$pp")" || {
    echo "CANNOT TELL — neither route answered for branch '$br'." >&2; return 1; }
  printf '%s' "$body" | jq -c \
    '. + {_transport:"per-workflow",
          _control:"⚠️ branch view has no per-commit coverage control; this count is a FLOOR"}'
}

# runs_api_epoch <repo> -> ISO8601 of the OLDEST run that exists; rc 0/1.
# Used only on the zero-runs path, to tell "CI never ran for this commit" from
# "CI ran and left nothing" — see check-citation.sh's Actions-epoch arm.
runs_api_epoch() {
  local repo="$1" ctrl body oldest="" wids w n d
  runs_api_require || return 1
  if ctrl="$(_runs_api_repo_wide "repos/$repo/actions/runs?per_page=1" )"; then
    n="$(printf '%s' "$ctrl" | jq -r '.total_count // 0')"
    if printf '%s' "$n" | grep -qE '^[0-9]+$' && [ "$n" -gt 0 ]; then
      body="$(_runs_api_repo_wide "repos/$repo/actions/runs?per_page=1&page=$n")" || return 1
      printf '%s' "$body" | jq -r '.workflow_runs[0].created_at // empty'; return 0
    fi
  fi
  # Fallback: the oldest run of any workflow IS the repo's Actions epoch.
  wids="$(_runs_api_workflow_ids "$repo")" || return 1
  while read -r w; do
    [ -n "$w" ] || continue
    body="$(_runs_api_raw "repos/$repo/actions/workflows/$w/runs?per_page=1")" || continue
    n="$(printf '%s' "$body" | jq -r '.total_count // 0')"
    printf '%s' "$n" | grep -qE '^[0-9]+$' || continue
    [ "$n" -gt 0 ] || continue
    body="$(_runs_api_raw "repos/$repo/actions/workflows/$w/runs?per_page=1&page=$n")" || continue
    d="$(printf '%s' "$body" | jq -r '.workflow_runs[0].created_at // empty')"
    [ -n "$d" ] || continue
    if [ -z "$oldest" ] || [ "$d" \< "$oldest" ]; then oldest="$d"; fi
  done <<< "$wids"
  [ -n "$oldest" ] || return 1
  printf '%s' "$oldest"
}

# runs_api_mode_banner <payload-json> — one line, printed by callers so the
# transport in use is never a thing the reader has to infer.
#
# ⚠️ IT TAKES THE PAYLOAD AS AN ARGUMENT, AND THAT IS THE WHOLE POINT. The
# header above records why the transport travels ON the emitted object rather
# than in a global: every caller invokes the query functions as `X="$(…)"`,
# which is a subshell, so an assignment made inside them is discarded.
#
# ⚠️ THAT FIX WAS HALF-LANDED AND THIS FUNCTION WAS THE MISSING HALF. The
# producers were moved to `_transport`/`_control` keys; this consumer was left
# reading `$RUNS_API_MODE`/`$RUNS_API_CONTROL_NOTE`, which NOTHING assigns.
# Under `set -u` — which check-citation.sh sets at :68 — that is not a wrong
# label, it is an `unbound variable` abort: the script died immediately after
# its positive control and printed no verdict at all. Found by RUNNING it;
# a reading of the header alone says the bug was already fixed.
#
# ⚠️ AND THE UNKNOWN ARM IS DELIBERATE. A caller that forgets to pass the
# payload must be told so, not silently reassured with the happy answer — a
# WRONG provenance is worse than an absent one, because nothing prompts a
# re-check. Defaulting to "repo-wide" here would have printed a normal-looking
# citation for an answer the fallback produced, which is exactly the failure
# the header describes catching once already.
runs_api_mode_banner() {
  local payload="${1:-}" transport control
  transport="$(printf '%s' "$payload" | jq -r '._transport // empty' 2>/dev/null)"
  control="$(printf '%s' "$payload" | jq -r '._control // empty' 2>/dev/null)"
  case "$transport" in
    per-workflow)
      echo "   · ⚠️ transport: PER-WORKFLOW FALLBACK (the repo-wide /actions/runs route did not answer)"
      [ -n "$control" ] && echo "     $control"
      ;;
    repo-wide)
      echo "   · transport: repo-wide /actions/runs"
      ;;
    *)
      echo "   · ⚠️ transport: UNKNOWN — no _transport key in the payload handed to the banner."
      echo "     The verdict below may be sound; its PROVENANCE is not established."
      ;;
  esac
  return 0
}
