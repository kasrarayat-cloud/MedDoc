#!/usr/bin/env bash
# ============================================================================
# check-citation.sh — a citation is PRODUCED by this script, never by hand.
# ----------------------------------------------------------------------------
# THE PREDICATE, in one sentence:
#
#   For the given FULL 40-character commit SHA, each of the four required
#   workflows has a run whose head_sha is EXACTLY that SHA, completed with
#   conclusion `success`; and in AUDIT mode, every run id a ledger row CLAIMS
#   belongs to that SHA and to a required workflow, and the claimed set equals
#   the found set.
#
# ── THE THREE DEFECTS THIS EXISTS TO KILL ──────────────────────────────────
#
# (a) SUBSTITUTION. A session wrote a citation row naming merge commit
#     0e04a759 with four run ids that belong to the PR HEAD 4d39493d. A
#     PR-head green is NEVER a citation for the merge commit. Nothing caught it.
#
#     ⚠️ AND THE OBVIOUS DEFENCE IS CIRCULAR. Enumerating the SHA's runs and
#     re-reading each one's head_sha proves nothing: `gh run list --commit` and
#     the REST `?head_sha=` filter are BOTH applied at the server, so the
#     readback asks the same question of an already-filtered set and its
#     mismatch count is 0 whether the system is healthy or broken. A first
#     draft of this file shipped that as "the point of the whole file".
#
#     The defence has to run the OTHER WAY: take the ids the ledger CLAIMS and
#     ask what commit each belongs to. That is --expect, and it is the only arm
#     that can see a substitution. PRODUCE mode prevents the defect at the
#     source; --expect is what audits a row that already exists (STEP 0.4).
#
# (b) THE ABBREVIATED SHA. `gh run list --commit <short-sha>` returns [] for
#     ANY abbreviated SHA — exit 0, no warning, no "ambiguous" — so an
#     in-flight run and an all-clear are the same output. Verified live:
#     748ec09a -> 0 runs; 748ec09aa4122652b42ea6be79745873ca57ba2d -> 4.
#     ARM 0 refuses anything that is not 40 hex characters.
#
# (c) ATTEMPT LAUNDERING. A re-run does NOT mint a new run id; it increments
#     run_attempt on the same one, and `gh run list` reports only the latest
#     attempt's conclusion. So "CI 31351013424: success" is true and hides a
#     failed attempt 1. Only `gh api .../actions/runs/<id> --jq .run_attempt`
#     can tell, and every line this script emits carries `a<attempt>`.
#
# ⚠️ `gh pr checks` IS NEVER USED HERE. It is recorded in AGENTS.md as
# unreliable — it reported `pending` for a run already completed/success. A
# citation must never be taken from it.
#
# Usage:
#   bash scripts/check-citation.sh <FULL-40-CHAR-SHA>
#   bash scripts/check-citation.sh <FULL-40-CHAR-SHA> --expect 123,456,789,012
#   bash scripts/check-citation.sh <FULL-40-CHAR-SHA> --repo owner/name
#
# Exit: 0 = citation complete   1 = FINDING   2 = cannot tell
#
# ⚠️ IT IS NOT A STANDING CHECK. Every sibling in STEP 0.5 takes no argument;
# this one REQUIRES a commit, so a bare invocation is a permanent untriageable
# 🟡. It belongs in STEP 0.4 (verify the previous session's citation) and at
# the moment a citation row is written — nowhere else.
# ============================================================================
set -uo pipefail

REQUIRED=(CI e2e a11y-ci secrets-scan)
REPO=""
SHA=""
EXPECT_RAW=""
# GitHub retains workflow runs for 90 days; past that, "no runs" means "cannot
# tell", never "was never cited". 85 days leaves margin for the boundary.
RETENTION_DAYS=85
# A commit pushed seconds ago legitimately has no runs yet.
PROPAGATION_SECS=300

die2() { echo "🟡 $*"; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    # ⚠️ `shift 2` with one argument left shifts NOTHING and returns non-zero,
    # so the loop spins forever. In an unattended session that is a HANG — the
    # one outcome the 0/1/2 convention exists to prevent.
    --repo)   [ $# -ge 2 ] || die2 "--repo needs a value"; REPO="$2"; shift 2 ;;
    --expect) [ $# -ge 2 ] || die2 "--expect needs a value"; EXPECT_RAW="$2"; shift 2 ;;
    -h|--help) sed -n '1,60p' "$0"; exit 2 ;;
    -*) die2 "unknown flag: $1" ;;
    *)  [ -n "$SHA" ] && die2 "more than one commit given: '$SHA' and '$1'"; SHA="$1"; shift ;;
  esac
done

# ── ARM 0 — THE ABBREVIATION REFUSAL. Defect (b). ──────────────────────────
[ -n "$SHA" ] || die2 "no commit given. Usage: check-citation.sh <FULL-40-CHAR-SHA> [--expect ids]"
if ! printf '%s' "$SHA" | grep -qE '^[0-9a-f]{40}$'; then
  n=${#SHA}
  echo "🟡 NOT A FULL SHA — '$SHA' is $n character(s); 40 lowercase hex are required."
  echo "   \`gh run list --commit\` returns [] for ANY abbreviation — exit 0, no warning —"
  echo "   so an abbreviated query cannot distinguish 'no runs' from 'not resolved'."
  echo "   Resolve it first:  git rev-parse $SHA"
  echo "   and paste the 40 characters into the ledger too."
  exit 2
fi

if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
  [ -n "$REPO" ] || die2 "cannot determine the repository (pass --repo owner/name)"
fi

echo "citation check — $REPO @ $SHA"

# ── POSITIVE CONTROL — a broken query and a clean commit look identical. ────
# Without this, every zero below is unfalsifiable: if gh were unauthenticated,
# rate-limited or pointed elsewhere, "no runs" would be the output for a
# perfectly cited commit. -R is passed HERE TOO; a control that runs against a
# different repository than the query guarantees nothing about the query.
CTRL="$(gh run list -R "$REPO" --limit 1 --json databaseId --jq 'length' 2>/dev/null)"
if [ -z "$CTRL" ] || [ "$CTRL" = "0" ]; then
  die2 "POSITIVE CONTROL FAILED — \`gh run list\` returns nothing at all for $REPO.
     Every zero this script could print would be meaningless. Check auth, the
     repo name, and rate limits before believing any answer here."
fi
echo "   · positive control: the run API answers for $REPO ($CTRL run visible)"

# ── The commit itself. Its AGE decides what "no runs" means. ────────────────
# ⚠️ `gh api` writes its ERROR BODY to stdout on 4xx, so a non-empty answer is
# NOT proof of success. Check the exit status, never the string.
CDATE=""
if COMMIT_JSON="$(gh api "repos/$REPO/commits/$SHA" --jq '.commit.committer.date' 2>/dev/null)"; then
  CDATE="$COMMIT_JSON"
fi
AGE_SECS=-1
if [ -n "$CDATE" ] && [ "$CDATE" != "null" ]; then
  CEPOCH="$(date -u -d "$CDATE" +%s 2>/dev/null)"
  [ -n "$CEPOCH" ] && AGE_SECS=$(( $(date -u +%s) - CEPOCH ))
fi

RUNS_TSV="$(gh run list -R "$REPO" --commit "$SHA" --limit 100 \
  --json databaseId,name,status,conclusion,headSha,event \
  --jq '.[] | [.databaseId, .name, .status, (.conclusion // "none"), .headSha, (.event // "none")] | join("\u001f")' 2>/dev/null)"
GH_RC=$?
[ $GH_RC -eq 0 ] || die2 "\`gh run list --commit\` failed (rc=$GH_RC) — cannot tell."

# TOTAL comes from the INPUT, not from the loop. If any line fails to bucket,
# SUM < TOTAL and the reconciliation below can actually FAIL — which is the
# whole point of asserting it.
TOTAL=0
[ -n "$RUNS_TSV" ] && TOTAL="$(printf '%s\n' "$RUNS_TSV" | grep -c .)"

if [ "$TOTAL" -eq 0 ]; then
  if [ -z "$CDATE" ] || [ "$CDATE" = "null" ]; then
    die2 "NO SUCH COMMIT in $REPO (or the API declined to describe it) — cannot tell."
  fi
  if [ "$AGE_SECS" -ge 0 ] && [ "$AGE_SECS" -lt "$PROPAGATION_SECS" ]; then
    die2 "no runs yet on a commit ${AGE_SECS}s old — that is the propagation window, not a finding. Re-check shortly."
  fi
  if [ "$AGE_SECS" -ge $(( RETENTION_DAYS * 86400 )) ]; then
    die2 "no runs visible on a commit committed $CDATE, which is past GitHub's ~90-day
     run retention. 'No runs now' does NOT mean 'never cited' — cannot tell."
  fi
  echo "🔴 NO RUN EXISTS on $SHA (committed $CDATE, inside the retention window)."
  echo "   If this commit is on main, it reached main uncited."
  exit 1
fi

GREEN=(); RED=(); PEND=(); FOREIGN=(); EXTRA=(); UNREAD=()
declare -A FOUND_ID=() FOUND_STATE=()

# ⚠️ IFS IS THE UNIT SEPARATOR (\037), NOT TAB. Tab is IFS *whitespace*, so bash
# collapses runs of it and an empty field silently shifts every later field one
# place left — which turned every in-flight run (empty conclusion) into a
# "foreign head" and made the PENDING bucket unreachable. A non-whitespace IFS
# preserves empty fields. The `// "none"` above is the second belt.
while IFS=$'\037' read -r id wf st cc hs ev; do
  [ -n "${id:-}" ] || { UNREAD+=("<unparseable line>"); continue; }
  if [ -z "${wf:-}" ] || [ -z "${hs:-}" ]; then UNREAD+=("$id"); continue; fi
  if ! printf '%s\n' "${REQUIRED[@]}" | grep -qxF "$wf"; then
    EXTRA+=("$wf $id ($st/$cc, event=$ev)"); continue
  fi
  # Cheap invariant, NOT the substitution defence — see (a) in the header. It
  # can only fire if `gh run list --commit` ever stops filtering by head_sha.
  if [ "$hs" != "$SHA" ]; then FOREIGN+=("$wf $id head=$hs"); continue; fi
  FOUND_ID["$wf"]="$id"
  if [ "$st" != "completed" ]; then PEND+=("$wf $id ($st)"); FOUND_STATE["$wf"]="pending"; continue; fi
  if [ "$cc" != "success" ]; then RED+=("$wf $id ($cc)"); FOUND_STATE["$wf"]="red"; continue; fi
  GREEN+=("$wf $id"); FOUND_STATE["$wf"]="green"
done <<< "$RUNS_TSV"

SUM=$(( ${#GREEN[@]} + ${#RED[@]} + ${#PEND[@]} + ${#FOREIGN[@]} + ${#EXTRA[@]} + ${#UNREAD[@]} ))
echo "   runs: $TOTAL = green ${#GREEN[@]} + red ${#RED[@]} + pending ${#PEND[@]} + foreign ${#FOREIGN[@]} + extra ${#EXTRA[@]} + unreadable ${#UNREAD[@]}"
if [ "$SUM" -ne "$TOTAL" ]; then
  die2 "BUCKETS DO NOT RECONCILE — $SUM sorted of $TOTAL listed. $(( TOTAL - SUM )) run(s) fell
     through every branch, so this script's own answer is not trustworthy."
fi

MISSING=()
for wf in "${REQUIRED[@]}"; do [ -n "${FOUND_ID[$wf]:-}" ] || MISSING+=("$wf"); done

[ ${#EXTRA[@]} -gt 0 ] && { echo "   · note — non-required workflows on this commit (not part of the citation):"; printf '        %s\n' "${EXTRA[@]}"; }

# ── ARM: --expect. THE SUBSTITUTION DEFENCE. Defect (a). ───────────────────
# Runs the query BACKWARDS: given the ids a ledger row claims, ask GitHub what
# commit each one belongs to. This is the only arm that can see a run id
# borrowed from another commit, because it never filters by head_sha.
SUBS=(); GHOST=(); NOTREQ=()
if [ -n "$EXPECT_RAW" ]; then
  EXPECT_IDS="$(printf '%s' "$EXPECT_RAW" | tr ',' '\n' | tr -d ' ' | grep -E '^[0-9]+$')"
  BADTOK="$(printf '%s' "$EXPECT_RAW" | tr ',' '\n' | tr -d ' ' | grep -vE '^[0-9]+$' | grep -c .)"
  [ "$BADTOK" -gt 0 ] && die2 "--expect must be bare run ids separated by commas. $BADTOK token(s) are not.
     A pasted run URL contains a JOB id too, and querying that 404s — which would
     read as 'this run does not exist' and accuse a correct row."
  [ -n "$EXPECT_IDS" ] || die2 "--expect parsed to no run ids at all."
  echo "   · auditing $(printf '%s\n' "$EXPECT_IDS" | grep -c .) claimed run id(s) against $SHA"
  while read -r cid; do
    [ -n "$cid" ] || continue
    if ! META="$(gh api "repos/$REPO/actions/runs/$cid" --jq '[.head_sha,.name,.run_attempt,.conclusion]|join("\u001f")' 2>/dev/null)"; then
      GHOST+=("$cid"); continue
    fi
    IFS=$'\037' read -r c_hs c_wf c_at c_cc <<< "$META"
    if [ "$c_hs" != "$SHA" ]; then SUBS+=("$cid ($c_wf) belongs to $c_hs — NOT $SHA"); continue; fi
    printf '%s\n' "${REQUIRED[@]}" | grep -qxF "$c_wf" || NOTREQ+=("$cid ($c_wf is not a required workflow)")
  done <<< "$EXPECT_IDS"

  CLAIMED_SORT="$(printf '%s\n' "$EXPECT_IDS" | sort -u)"
  FOUND_SORT="$(for wf in "${REQUIRED[@]}"; do [ -n "${FOUND_ID[$wf]:-}" ] && echo "${FOUND_ID[$wf]}"; done | sort -u)"
  SETDIFF="$(comm -3 <(printf '%s\n' "$CLAIMED_SORT") <(printf '%s\n' "$FOUND_SORT") | tr -d '\t' | grep -c . || true)"
fi

# ── VERDICT. Findings and can't-tells are kept DISTINCT and never merged. ──
RC=0
if [ ${#FOREIGN[@]} -gt 0 ]; then
  echo "🔴 FOREIGN HEAD — $((${#FOREIGN[@]})) run(s) listed under $SHA report a different head_sha."
  printf '     %s\n' "${FOREIGN[@]}"
  echo "   This should be impossible (the query filters by head_sha). Treat the tooling as suspect."
  RC=1
fi
if [ ${#SUBS[@]} -gt 0 ]; then
  echo "🔴 SUBSTITUTION — the row claims run id(s) that belong to another commit:"
  printf '     %s\n' "${SUBS[@]}"
  echo "   A PR-head green is NEVER a citation for the merge commit. Re-take the"
  echo "   citation from this commit's OWN runs — the block below, if it is green."
  RC=1
fi
[ ${#GHOST[@]} -gt 0 ] && { echo "🔴 CLAIMED RUN DOES NOT EXIST: ${GHOST[*]}"; RC=1; }
[ ${#NOTREQ[@]} -gt 0 ] && { echo "🔴 CLAIMED RUN IS NOT A REQUIRED WORKFLOW:"; printf '     %s\n' "${NOTREQ[@]}"; RC=1; }
if [ -n "$EXPECT_RAW" ] && [ "${SETDIFF:-0}" -gt 0 ] && [ ${#SUBS[@]} -eq 0 ] && [ ${#GHOST[@]} -eq 0 ]; then
  echo "🔴 CLAIMED SET != FOUND SET — the row's ids are not this commit's four required runs."
  RC=1
fi
[ ${#RED[@]} -gt 0 ] && { echo "🔴 REQUIRED WORKFLOW FAILED:"; printf '     %s\n' "${RED[@]}"; RC=1; }

if [ ${#PEND[@]} -gt 0 ]; then
  echo "🟡 STILL RUNNING — not a citation YET, and not a finding. WAIT."
  printf '     %s\n' "${PEND[@]}"
  [ "$RC" -eq 0 ] && RC=2
fi
if [ ${#MISSING[@]} -gt 0 ]; then
  if [ "$AGE_SECS" -ge 0 ] && [ "$AGE_SECS" -lt "$PROPAGATION_SECS" ]; then
    echo "🟡 NOT ALL REQUIRED WORKFLOWS HAVE STARTED on a commit ${AGE_SECS}s old: ${MISSING[*]}"
    [ "$RC" -eq 0 ] && RC=2
  else
    echo "🔴 REQUIRED WORKFLOW MISSING on a commit $(( AGE_SECS / 60 )) minute(s) old: ${MISSING[*]}"
    RC=1
  fi
fi

if [ "$RC" -ne 0 ]; then
  if [ ${#GREEN[@]} -eq ${#REQUIRED[@]} ]; then
    echo
    echo "   ⚠️ NOTE: the COMMIT is fully green — it is the ROW that is wrong."
    echo "      Do not read this as 'do not deploy'. Replace the row with the block below."
  else
    echo
    echo "   A partial citation is not a citation."
  fi
fi

# ── THE CITATION BLOCK. Full SHA, and every attempt named. Defect (c). ─────
if [ ${#GREEN[@]} -eq ${#REQUIRED[@]} ]; then
  echo
  echo "**Citation — ${#GREEN[@]} of ${#REQUIRED[@]} on \`$SHA\`:**"
  RERUN=0
  for wf in "${REQUIRED[@]}"; do
    id="${FOUND_ID[$wf]}"
    at="$(gh api "repos/$REPO/actions/runs/$id" --jq '.run_attempt' 2>/dev/null)"
    if [ -z "$at" ]; then
      echo "   · \`$wf\` $id a? — ATTEMPT UNREADABLE"
      RC=2
    else
      echo "   · \`$wf\` $id a$at"
      [ "$at" -gt 1 ] && RERUN=1
    fi
  done
  if [ "$RERUN" -eq 1 ]; then
    echo
    echo "   ⚠️ AT LEAST ONE RUN IS ON A RE-RUN (a>1). The run id alone would have"
    echo "      hidden that. Say in the row WHY it was re-run — canon forbids"
    echo "      re-run-and-hope, so an unexplained a2 is a finding of its own."
  fi
  [ "$RC" -eq 0 ] && echo && echo "🟢 CITATION COMPLETE."
fi

exit "$RC"
