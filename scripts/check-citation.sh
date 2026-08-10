#!/usr/bin/env bash
# ============================================================================
# check-citation.sh — a citation is PRODUCED by this script, never typed.
# ----------------------------------------------------------------------------
# THE PREDICATE, in one sentence:
#
#   For the given FULL 40-character commit SHA, each of the four required
#   workflows has EXACTLY ONE chosen run on that SHA, completed with conclusion
#   `success`; and in AUDIT mode, every run id a ledger row CLAIMS belongs to
#   that SHA and to a required workflow, and the claimed set is exactly the set
#   of chosen runs.
#
# ── THE THREE DEFECTS IT EXISTS TO KILL ────────────────────────────────────
#
# (a) SUBSTITUTION. Session 02 cited merge commit 0e04a759 with four run ids
#     belonging to PR head 4d39493d. Nothing caught it.
#     ⚠️ THE OBVIOUS DEFENCE IS CIRCULAR. Enumerating a SHA's runs and
#     re-reading each head_sha asks the server the same question about an
#     already-filtered set: its mismatch count is 0 whether the system is
#     healthy or broken. The defence has to run the OTHER WAY — take the ids
#     the ROW claims and ask what commit each belongs to. That is --expect.
#
# (b) THE ABBREVIATED SHA. `gh run list --commit <short>` returns [] for ANY
#     abbreviation, exit 0, no warning. ARM 0 refuses non-40-hex.
#
# (c) ATTEMPT LAUNDERING. A re-run increments run_attempt on the SAME id, and
#     the run list reports only the latest attempt. Every emitted line carries
#     a<attempt>; a>1 demands a written reason.
#
# ── WHAT AN ADVERSARIAL PASS BROKE IN THE PREVIOUS VERSION ─────────────────
# Recorded because each one is a rule this file now obeys, and because a
# reviewer should be able to check they are actually closed:
#
#   · a detected SUBSTITUTION exited 2, not 1 — an UNGUARDED `RC=2` on the
#     attempt readback. EVERY rc-2 assignment here is `[ "$RC" -eq 0 ] && RC=2`.
#   · `🟢 CITATION COMPLETE` with runs bucketed "unreadable". A nameless run
#     (`name:""`, conclusion `startup_failure`) is GitHub's marker for a
#     workflow file that failed to parse — i.e. exactly how a REQUIRED workflow
#     silently never runs. UNREADABLE is now a cannot-tell, never ignored.
#   · an 85-day "retention cliff" that auto-excused ~78 merge commits. Run
#     RECORDS are not pruned at 90 days (only logs/artifacts). The floor is now
#     the repo's ACTUAL Actions epoch, read from the oldest run that exists.
#   · `cancelled` reported as FAILED. A cancelled run usually means a later
#     push destroyed the evidence — this repo's most documented class — and the
#     answer is "cite the descendant", not "a gate failed".
#   · a run queued since a GitHub incident four days earlier reported "WAIT"
#     forever. Pending now has a staleness bound.
#   · silent truncation at 100 runs, making required workflows look MISSING.
#     Fetched via the REST endpoint so `total_count` is known and asserted.
#   · the citation block gated on a count of RUNS vs a count of WORKFLOWS, so a
#     duplicate run either suppressed the block entirely or cited a FAILED run.
#     Everything is keyed BY WORKFLOW now, and the block is gated on RC -eq 0.
#
# ⚠️ `gh pr checks` IS NEVER USED. AGENTS.md records it reporting `pending` for
# a run already completed/success.
#
# Usage:
#   bash scripts/check-citation.sh <FULL-40-CHAR-SHA>
#   bash scripts/check-citation.sh <FULL-40-CHAR-SHA> --expect 123,456,789,012
#   bash scripts/check-citation.sh <FULL-40-CHAR-SHA> --repo owner/name
#
# Exit: 0 = citation complete   1 = FINDING   2 = cannot tell
#
# ⚠️ NOT A STANDING CHECK. It requires a commit argument, so a bare invocation
# would be a permanent untriageable amber in STEP 0.5. It belongs in STEP 0.4
# and at the moment a citation row is written.
# ============================================================================
set -uo pipefail

REQUIRED=(CI e2e a11y-ci secrets-scan)
REPO=""; SHA=""; EXPECT_RAW=""
PROPAGATION_SECS=300      # a commit pushed seconds ago legitimately has no runs
STALE_PENDING_SECS=10800  # 3h: past this, "in progress" is a zombie, not a wait
PAGE=100

RC=0
note() { echo "$@"; }
fail() { echo "🔴 $*"; RC=1; }
cant() { echo "🟡 $*"; [ "$RC" -eq 0 ] && RC=2; return 0; }
die2() { echo "🟡 $*"; exit 2; }

# api_get <path> <jq> -> stdout body; rc 0 ok, 3 = 404 (authoritative absence),
# 4 = any other failure (transient/rate-limit/network) which is a CANNOT TELL.
# ⚠️ The distinction is the whole point: the previous version mapped every
# non-zero gh exit to "this run does not exist", so one 500 accused a correct
# ledger row of the substitution defect.
api_get() {
  local out err rc
  err="$(mktemp)"
  out="$(gh api "$1" --jq "$2" 2>"$err")"; rc=$?
  if [ $rc -ne 0 ]; then
    # 3 = AUTHORITATIVE ABSENCE. GitHub says 404 for a missing run, but 422
    # "No commit found for SHA" for a well-formed commit that does not exist —
    # both are the server telling us the thing is not there, and neither is a
    # transient. Anything else is a cannot-tell.
    if grep -qE 'HTTP 404|Not Found|No commit found for SHA' "$err"; then rm -f "$err"; return 3; fi
    rm -f "$err"; return 4
  fi
  rm -f "$err"; printf '%s' "$out"; return 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    # `shift 2` with one arg left shifts NOTHING and returns non-zero -> the
    # loop spins forever. In an unattended session that is a HANG.
    --repo)   [ $# -ge 2 ] || die2 "--repo needs a value"; REPO="$2"; shift 2 ;;
    --expect) [ $# -ge 2 ] || die2 "--expect needs a value"; EXPECT_RAW="$2"; shift 2 ;;
    -h|--help) sed -n '1,67p' "$0"; exit 2 ;;
    -*) die2 "unknown flag: $1" ;;
    *)  [ -n "$SHA" ] && die2 "more than one commit given: '$SHA' and '$1'"; SHA="$1"; shift ;;
  esac
done

# ── ARM 0 — THE ABBREVIATION REFUSAL. Defect (b). ──────────────────────────
[ -n "$SHA" ] || die2 "no commit given. Usage: check-citation.sh <FULL-40-CHAR-SHA> [--expect ids]"
if ! printf '%s' "$SHA" | grep -qE '^[0-9a-f]{40}$'; then
  if printf '%s' "$SHA" | grep -qiE '^[0-9a-f]{40}$'; then
    die2 "NOT A FULL SHA — '$SHA' is 40 hex characters but not all lowercase.
     GitHub's APIs are case-sensitive here. Lowercase it:  git rev-parse ${SHA}"
  fi
  die2 "NOT A FULL SHA — '$SHA' is ${#SHA} character(s); 40 lowercase hex are required.
     \`gh run list --commit\` returns [] for ANY abbreviation — exit 0, no warning —
     so an abbreviated query cannot tell 'no runs' from 'not resolved'.
     Resolve it first:  git rev-parse $SHA
     and paste the 40 characters into the ledger too."
fi

if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
  [ -n "$REPO" ] || die2 "cannot determine the repository (pass --repo owner/name)"
fi
echo "citation check — $REPO @ $SHA"

# ── POSITIVE CONTROL — on BOTH transports. ─────────────────────────────────
# The previous version controlled only the run-list path, so every failure of
# the REST path (which --expect and the attempt readback both use) was
# invisible to it. A broken query and a clean commit print the same zero.
CTRL="$(api_get "repos/$REPO/actions/runs?per_page=1" '.total_count')" || \
  die2 "POSITIVE CONTROL FAILED — the runs API does not answer for $REPO.
     Every zero below would be meaningless. Check auth, repo name, rate limits."
[ -n "$CTRL" ] && [ "$CTRL" != "0" ] || \
  die2 "POSITIVE CONTROL FAILED — $REPO reports zero workflow runs in total."
echo "   · positive control: runs API answers for $REPO ($CTRL runs total)"

# ── The commit. Its date decides what "no runs" MEANS. ─────────────────────
CDATE="$(api_get "repos/$REPO/commits/$SHA" '.commit.committer.date')"; CRC=$?
AGE=-1
if [ $CRC -eq 0 ] && [ -n "$CDATE" ] && [ "$CDATE" != "null" ]; then
  CE="$(date -u -d "$CDATE" +%s 2>/dev/null)"
  [ -n "$CE" ] && AGE=$(( $(date -u +%s) - CE ))
fi

# ── The runs, via REST so total_count is KNOWN. ────────────────────────────
RUNS_JSON="$(api_get "repos/$REPO/actions/runs?head_sha=$SHA&per_page=$PAGE" '.')" \
  || die2 "could not list runs for $SHA — cannot tell."
TOTAL="$(printf '%s' "$RUNS_JSON" | jq -r '.total_count')"
FETCHED="$(printf '%s' "$RUNS_JSON" | jq -r '.workflow_runs | length')"
[ -n "$TOTAL" ] && [ "$TOTAL" != "null" ] || die2 "the runs API returned no total_count — cannot tell."

# ⚠️ TRUNCATION IS A CANNOT-TELL, NOT A MISSING WORKFLOW. Three commits in this
# repo carry >100 runs (dependabot-heavy) with every required run on page 2.
# The previous version reported `REQUIRED WORKFLOW MISSING` on all of them.
if [ "$TOTAL" -gt "$FETCHED" ]; then
  die2 "TRUNCATED — $TOTAL runs on this commit, $FETCHED fetched (page size $PAGE).
     The required runs may be outside the window, so any verdict here would be
     about a subset nobody chose. Cannot tell."
fi

# ── AUDIT (--expect) RUNS FIRST, BEFORE any early exit. ────────────────────
# ⚠️ The previous version placed it AFTER the zero-runs exit, so the only arm
# that can see a substitution was skipped in exactly the state that most
# invites one: a session borrows another commit's runs BECAUSE this one has none.
declare -A CLAIM_WF=()
SUBS=(); GHOST=(); UNSURE=(); NOTREQ=(); CLAIMED=()
if [ -n "$EXPECT_RAW" ]; then
  BAD="$(printf '%s' "$EXPECT_RAW" | tr ',' '\n' | tr -d ' ' | grep -vE '^[0-9]+$' | grep -c . || true)"
  [ "$BAD" -gt 0 ] && die2 "--expect takes bare run ids separated by commas; $BAD token(s) are not.
     A pasted run URL also contains a JOB id, and querying that 404s — which would
     read as 'this run does not exist' and accuse a correct row."
  mapfile -t CLAIMED < <(printf '%s' "$EXPECT_RAW" | tr ',' '\n' | tr -d ' ' | grep -E '^[0-9]+$' | sort -u)
  [ "${#CLAIMED[@]}" -gt 0 ] || die2 "--expect parsed to no run ids at all."
  echo "   · auditing ${#CLAIMED[@]} claimed run id(s) against this commit"
  for cid in "${CLAIMED[@]}"; do
    META="$(api_get "repos/$REPO/actions/runs/$cid" '[.head_sha,.name]|join("|")')"; r=$?
    if [ $r -eq 3 ]; then GHOST+=("$cid"); continue; fi
    if [ $r -ne 0 ]; then UNSURE+=("$cid"); continue; fi
    c_hs="${META%%|*}"; c_wf="${META#*|}"
    if [ "$c_hs" != "$SHA" ]; then SUBS+=("$cid ($c_wf) belongs to $c_hs"); continue; fi
    if printf '%s\n' "${REQUIRED[@]}" | grep -qxF "$c_wf"; then CLAIM_WF["$c_wf"]="$cid"
    else NOTREQ+=("$cid ($c_wf is not a required workflow)"); fi
  done
fi

# ── Zero runs: what it means depends on the repo's ACTIONS EPOCH. ──────────
if [ "$TOTAL" -eq 0 ]; then
  [ ${#SUBS[@]} -gt 0 ] && { fail "SUBSTITUTION — and this commit has NO runs of its own:"; printf '     %s\n' "${SUBS[@]}"; }
  if [ $CRC -eq 3 ]; then die2 "NO SUCH COMMIT in $REPO — cannot tell."; fi
  if [ $CRC -ne 0 ] || [ "$AGE" -lt 0 ]; then die2 "could not read this commit's date — cannot tell whether 'no runs' is a finding."; fi
  if [ "$AGE" -lt "$PROPAGATION_SECS" ]; then die2 "no runs yet on a commit ${AGE}s old — the propagation window, not a finding."; fi
  # The floor is where this repo's Actions history BEGINS, read from the oldest
  # run that exists. Run records are NOT pruned at 90 days; assuming they were
  # excused every commit older than the cliff.
  OLDEST="$(api_get "repos/$REPO/actions/runs?per_page=1&page=$CTRL" '.workflow_runs[0].created_at')" || \
    die2 "no runs on this commit, and the repo's Actions epoch could not be read — cannot tell."
  OE="$(date -u -d "$OLDEST" +%s 2>/dev/null)"; CE2="$(date -u -d "$CDATE" +%s 2>/dev/null)"
  if [ -n "$OE" ] && [ -n "$CE2" ] && [ "$CE2" -lt "$OE" ]; then
    die2 "no runs, and this commit ($CDATE) PREDATES the repo's oldest workflow run
     ($OLDEST). CI did not exist for it — cannot tell, and not a finding."
  fi
  fail "NO RUN EXISTS on $SHA (committed $CDATE, after this repo's Actions epoch $OLDEST).
   If this commit is on main, it reached main uncited.
   ⚠️ CAVEAT, and check it before acting: the epoch is repo-wide, not per-workflow.
      A required workflow ADDED after this commit could not have run on it —
      a11y-ci, for instance, was added 2026-08-05. Confirm each required
      workflow FILE existed at $CDATE (\`git log -- .github/workflows/\`) before
      calling this uncited. This tool is built for auditing RECENT citations."
  exit "$RC"
fi

# ── Bucket BY WORKFLOW. Every run lands in exactly one class. ──────────────
declare -A WF_RUNS=() WF_GREEN=()
GREENC=0; REDC=0; PENDC=0; STALEC=0; CANC=0; STARTC=0; FOREIGNC=0; EXTRAC=0; UNREADC=0
EXTRA=(); REDS=(); PENDS=(); STALES=(); CANS=(); STARTS=(); FOREIGNS=(); UNREADS=()
NOW="$(date -u +%s)"

while IFS='|' read -r id wf st cc hs ev created; do
  [ -n "${id:-}" ] || continue
  if [ -z "${wf:-}" ]; then
    UNREADC=$((UNREADC+1)); UNREADS+=("$id (no workflow name; conclusion=${cc:-none}, event=${ev:-none})"); continue
  fi
  if ! printf '%s\n' "${REQUIRED[@]}" | grep -qxF "$wf"; then
    EXTRAC=$((EXTRAC+1)); EXTRA+=("$wf $id ($st/${cc:-none}, event=$ev)"); continue
  fi
  if [ "$hs" != "$SHA" ]; then FOREIGNC=$((FOREIGNC+1)); FOREIGNS+=("$wf $id head=$hs"); continue; fi
  WF_RUNS["$wf"]="${WF_RUNS[$wf]:-} $id"
  if [ "$st" != "completed" ]; then
    ce="$(date -u -d "$created" +%s 2>/dev/null)"; age=-1
    [ -n "$ce" ] && age=$(( NOW - ce ))
    if [ "$age" -ge 0 ] && [ "$age" -ge "$STALE_PENDING_SECS" ]; then
      STALEC=$((STALEC+1)); STALES+=("$wf $id ($st for $(( age / 3600 ))h — will it ever finish?)")
    else
      PENDC=$((PENDC+1)); PENDS+=("$wf $id ($st)")
    fi
    continue
  fi
  case "$cc" in
    success)         GREENC=$((GREENC+1)); WF_GREEN["$wf"]="${WF_GREEN[$wf]:-} $id" ;;
    cancelled)       CANC=$((CANC+1));   CANS+=("$wf $id") ;;
    startup_failure) STARTC=$((STARTC+1)); STARTS+=("$wf $id") ;;
    *)               REDC=$((REDC+1));   REDS+=("$wf $id ($cc)") ;;
  esac
done < <(printf '%s' "$RUNS_JSON" | jq -r '.workflow_runs[] | [(.id|tostring), (.name // ""), .status, (.conclusion // "none"), .head_sha, (.event // "none"), .created_at] | join("|")')

SUM=$(( GREENC + REDC + PENDC + STALEC + CANC + STARTC + FOREIGNC + EXTRAC + UNREADC ))
echo "   runs: $TOTAL = green $GREENC + red $REDC + pending $PENDC + stale $STALEC + cancelled $CANC + startup-fail $STARTC + foreign $FOREIGNC + extra $EXTRAC + unreadable $UNREADC"
# Falsifiable: TOTAL comes from the API, SUM from the buckets. They diverge if
# jq drops a row, if a name contains the separator, or if a class is unhandled.
if [ "$SUM" -ne "$TOTAL" ]; then
  die2 "BUCKETS DO NOT RECONCILE — $SUM sorted of $TOTAL reported by the API.
     This script's own answer is not trustworthy. Cannot tell."
fi
[ "$EXTRAC" -gt 0 ] && { note "   · note — non-required workflows here (not part of the citation):"; printf '        %s\n' "${EXTRA[@]}"; }

# ── Choose ONE run per required workflow. Duplicates need --expect. ────────
declare -A CHOSEN=()
DUPES=(); MISSING=()
for wf in "${REQUIRED[@]}"; do
  read -r -a greens <<< "${WF_GREEN[$wf]:-}"
  read -r -a allr   <<< "${WF_RUNS[$wf]:-}"
  if [ "${#allr[@]}" -eq 0 ]; then MISSING+=("$wf"); continue; fi
  if [ -n "${CLAIM_WF[$wf]:-}" ]; then CHOSEN["$wf"]="${CLAIM_WF[$wf]}"; continue; fi
  if [ "${#greens[@]}" -eq 1 ]; then CHOSEN["$wf"]="${greens[0]}"
  elif [ "${#greens[@]}" -gt 1 ]; then DUPES+=("$wf has ${#greens[@]} successful runs: ${greens[*]}")
  fi
done

# ── VERDICTS. Findings (1) and cannot-tells (2) never merge. ───────────────
[ "$FOREIGNC" -gt 0 ] && { fail "FOREIGN HEAD — runs listed under $SHA report another head_sha:"; printf '     %s\n' "${FOREIGNS[@]}"; }
[ ${#SUBS[@]}   -gt 0 ] && { fail "SUBSTITUTION — the row claims run id(s) belonging to another commit:"; printf '     %s\n' "${SUBS[@]}"
                             note "   A PR-head green is NEVER a citation for the merge commit."; }
[ ${#GHOST[@]}  -gt 0 ] && fail "CLAIMED RUN DOES NOT EXIST (GitHub answered 404): ${GHOST[*]}"
[ ${#NOTREQ[@]} -gt 0 ] && { fail "CLAIMED RUN IS NOT A REQUIRED WORKFLOW:"; printf '     %s\n' "${NOTREQ[@]}"; }
[ ${#UNSURE[@]} -gt 0 ] && cant "COULD NOT VERIFY claimed run id(s) — the API did not answer: ${UNSURE[*]}
     That is a cannot-tell, NOT evidence the row is wrong."
[ "$REDC"    -gt 0 ] && { fail "REQUIRED WORKFLOW FAILED:"; printf '     %s\n' "${REDS[@]}"; }
[ ${#STARTS_LIVE[@]} -gt 0 ] && { fail "REQUIRED WORKFLOW FAILED TO START (startup_failure), with no success to supersede it:"; printf '     %s\n' "${STARTS_LIVE[@]}"
                          note "   The workflow file did not parse, so the gate never ran at all."; }
# ⚠️ A cancelled or failed-to-start run whose workflow ALSO has a success on this
# SHA is SUPERSEDED NOISE, not a cannot-tell: the requirement is satisfied by the
# green one. Only the ones leaving their workflow without a green can withhold a
# citation. Without this the normal push-cancels-then-reruns pattern would make
# every such commit un-citable.
CANS_LIVE=(); for e in "${CANS[@]:-}"; do [ -n "$e" ] || continue; w="${e%% *}"; [ -n "${WF_GREEN[$w]:-}" ] || CANS_LIVE+=("$e"); done
STARTS_LIVE=(); for e in "${STARTS[@]:-}"; do [ -n "$e" ] || continue; w="${e%% *}"; [ -n "${WF_GREEN[$w]:-}" ] || STARTS_LIVE+=("$e"); done
SUP=$(( CANC + STARTC - ${#CANS_LIVE[@]} - ${#STARTS_LIVE[@]} ))
[ "$SUP" -gt 0 ] && note "   · note — $SUP cancelled/startup-failed run(s) are superseded by a success of the same workflow on this commit"

[ "$UNREADC" -gt 0 ] && cant "UNREADABLE RUN(S) — no workflow name, so they cannot be excluded from
     the required set. A nameless run is GitHub's marker for a workflow file that
     failed to parse, which is how a REQUIRED gate silently never runs:
$(printf '     %s\n' "${UNREADS[@]}")"
[ ${#CANS_LIVE[@]} -gt 0 ] && cant "CANCELLED RUN(S) leaving their workflow with NO success on this commit:
$(printf '     %s\n' "${CANS_LIVE[@]}")
     If a descendant commit carries a full citation, cite THE DESCENDANT.
     A cancelled gate is destroyed evidence, never a red gate."
[ "$STALEC"  -gt 0 ] && cant "STALE RUN(S) — pending far longer than any real run takes. These do not
     complete on their own; a zombie is not something to wait for:
$(printf '     %s\n' "${STALES[@]}")"
[ "$PENDC"   -gt 0 ] && cant "STILL RUNNING — not a citation YET, and not a finding. WAIT.
$(printf '     %s\n' "${PENDS[@]}")"
[ ${#DUPES[@]} -gt 0 ] && cant "DUPLICATE RUNS of a required workflow — which one does the row mean?
$(printf '     %s\n' "${DUPES[@]}")
     Re-run with --expect naming the intended id per workflow."
if [ ${#MISSING[@]} -gt 0 ]; then
  if [ "$AGE" -ge 0 ] && [ "$AGE" -lt "$PROPAGATION_SECS" ]; then
    cant "NOT ALL REQUIRED WORKFLOWS HAVE STARTED on a commit ${AGE}s old: ${MISSING[*]}"
  elif [ "$AGE" -lt 0 ]; then
    cant "REQUIRED WORKFLOW ABSENT (${MISSING[*]}) and the commit's age is unknown,
     so this cannot be told apart from the propagation window. Cannot tell."
  else
    fail "REQUIRED WORKFLOW MISSING on a commit $(( AGE / 60 )) minute(s) old: ${MISSING[*]}"
  fi
fi
# Set equality — only meaningful once every claimed id was verified.
if [ -n "$EXPECT_RAW" ] && [ ${#SUBS[@]} -eq 0 ] && [ ${#GHOST[@]} -eq 0 ] && [ ${#UNSURE[@]} -eq 0 ]; then
  CH="$(for wf in "${REQUIRED[@]}"; do [ -n "${CHOSEN[$wf]:-}" ] && echo "${CHOSEN[$wf]}"; done | sort -u)"
  CL="$(printf '%s\n' "${CLAIMED[@]}" | sort -u)"
  if [ "$CH" != "$CL" ]; then
    fail "CLAIMED SET != CHOSEN SET — the row's ids are not this commit's required runs."
    note "     claimed: $(printf '%s ' "${CLAIMED[@]}")"
    note "     chosen : $(echo "$CH" | tr '\n' ' ')"
  fi
fi

# ── THE CITATION BLOCK — emitted ONLY when the verdict is clean. ───────────
# ⚠️ Gated on RC, never on an arithmetic coincidence. The previous version
# gated on (green count == required count) and so printed paste-ready blocks
# naming failed runs, in-flight runs, and commits missing two workflows.
if [ "$RC" -ne 0 ]; then
  echo
  echo "   NO CITATION EMITTED — resolve the above first. A partial or unverified"
  echo "   citation is not a citation, and must not be pasted into a ledger row."
  exit "$RC"
fi
for wf in "${REQUIRED[@]}"; do
  [ -n "${CHOSEN[$wf]:-}" ] || { cant "internal: no chosen run for $wf"; }
done
[ "$RC" -eq 0 ] || exit "$RC"

echo
echo "**Citation — ${#REQUIRED[@]} of ${#REQUIRED[@]} on \`$SHA\`:**"
RERUN=0
for wf in "${REQUIRED[@]}"; do
  id="${CHOSEN[$wf]:-}"
  at="$(api_get "repos/$REPO/actions/runs/$id" '.run_attempt')"; r=$?
  # ⚠️ `gh api --jq` does NOT apply the filter to an error body, so a failed
  # call yields non-empty JSON garbage. An emptiness test would pass it straight
  # into the ledger row as `a{"message":...}` and silently disable defect (c).
  if [ $r -ne 0 ] || ! printf '%s' "$at" | grep -qE '^[0-9]+$'; then
    echo "   · \`$wf\` $id a? — ATTEMPT UNREADABLE"
    cant "the attempt number could not be read; this is not a citation yet."
    continue
  fi
  echo "   · \`$wf\` $id a$at"
  [ "$at" -gt 1 ] && RERUN=1
done
if [ "$RERUN" -eq 1 ]; then
  echo
  echo "   ⚠️ AT LEAST ONE RUN IS ON A RE-RUN (a>1). The run id alone hides that."
  echo "      The row must say WHY it was re-run — canon forbids re-run-and-hope,"
  echo "      so an unexplained re-run is a finding of its own."
fi
[ "$RC" -eq 0 ] && { echo; echo "🟢 CITATION COMPLETE."; }
exit "$RC"
