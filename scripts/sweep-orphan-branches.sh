#!/usr/bin/env bash
# ============================================================================
# F29 — ORPHAN-BRANCH SWEEP. READ-ONLY.
#   0 = nothing orphaned   1 = FINDING (unlanded work on origin)   2 = can't tell
# ----------------------------------------------------------------------------
# WHY: a branch pushed and never PR'd is INVISIBLE. Nothing lists it, nothing
# fails, and the work simply does not exist as far as `main` is concerned. Two
# bites in one session, both PRODUCTION RECORDS:
#
#   docs/f24-s3-judged            the judgement of a production deploy (#806)
#   docs/deploy-judged-acc4e4ef   the judgement of the F24-S5 migration deploy (#847)
#
# A deploy that is judged and whose judgement never reaches `main` is, to every
# future reader, a deploy that was never judged.
#
# ⚠️ THE PREDICATE IS PATCH-EQUIVALENCE, NOT "HAS NO PR", AND NOT COMMIT COUNT.
# The ledger sketched this sweep as "no open PR and no merged PR -> FLAG IT".
# Measured against origin on 2026-08-26 that flags 25 branches, of which only 9
# carry anything at all — a 64% false-positive rate, and a sweep that cries wolf
# 16 times is a sweep nobody reads by the third night.
#
# The naive refinement is worse, not better. `git rev-list --count main..BRANCH`
# said ALL 25 carried unlanded commits, because a SQUASH MERGE leaves the
# original commits unreachable while their content is fully in `main`. That is
# the canon's own trap — "A CENSUS IS ONLY AS AUTHORITATIVE AS ITS PREDICATE'S
# FIDELITY TO THE SHIPPED FUNCTION" — counting COMMITS to answer a question
# about WORK.
#
# `git cherry` compares by PATCH-ID, so squashed, rebased and cherry-picked
# content all read as landed. It answers the question actually being asked:
# is there anything HERE that is not THERE?
#
# ⚠️ AND THE HEALTHY ANSWER IS ZERO, WHICH IS EXACTLY WHY IT POSITIVE-CONTROLS.
# A zero from a broken enumeration and a zero from a clean remote are the same
# character. This refuses to print a zero it has not earned: if the branch list
# comes back empty, or `main` will not resolve, it exits 2 — never 0.
#
# ⚠️ TREE-RELATIVE ON PURPOSE (F28): it resolves the repo from its OWN location,
# so a persisted `cd` cannot silently point it at another checkout. Its subject
# is `origin`, which every worktree of this repo shares, so any of them answers
# identically — that is a property of the question, not an accident.
# ============================================================================
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${SWEEP_BASE:-origin/main}"

git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1 || {
  echo "🟡 CANNOT TELL — $REPO_DIR is not a git repository"
  exit 2
}

if [ "${SWEEP_SKIP_FETCH:-}" != "1" ]; then
  git -C "$REPO_DIR" fetch --prune --quiet origin 2>/dev/null || {
    echo "🟡 CANNOT TELL — could not fetch origin"
    exit 2
  }
fi

git -C "$REPO_DIR" rev-parse --verify --quiet "$BASE" >/dev/null || {
  echo "🟡 CANNOT TELL — base ref '$BASE' does not resolve"
  exit 2
}

# ---- enumerate, then POSITIVE-CONTROL the enumeration ----------------------
ALL="$(git -C "$REPO_DIR" branch -r --format='%(refname:short)' \
       | grep -v 'HEAD' | sed 's|^origin/||' | sort -u)"

TOTAL="$(printf '%s\n' "$ALL" | grep -c . )"
if [ "$TOTAL" -lt 2 ]; then
  echo "🟡 CANNOT TELL — enumerated $TOTAL remote branches, which cannot be right"
  echo "   (a broken enumeration and a tidy remote produce the same zero)"
  exit 2
fi

# dependabot branches are churn the bot owns and retires; `main` is the base.
SCOPE="$(printf '%s\n' "$ALL" | grep -v '^main$' | grep -v '^dependabot/')"
IN_SCOPE="$(printf '%s\n' "$SCOPE" | grep -c . )"

echo "orphan-branch sweep — base $BASE"
echo "   · $TOTAL remote branches, $IN_SCOPE in scope (excludes main + dependabot/*)"

# ⚠️ SWEEP_PROBE STOPS HERE — BEFORE ANY NETWORK CALL AT ALL, and the placement
# was moved twice before it was right. It exists so a test can positive-control
# the local guards (base resolves, enumeration non-empty, scope computed) without
# touching GitHub.
#
# v1 had no seam: the arm drove the whole sweep and timed out at 124 s.
# v2 put the seam after the PR-ref query below — one call, ~5 s, which sat exactly
#    on vitest's 5000 ms default. It passed at 4.8 s and failed at 5.1 s on the
#    very next run. A CI arm whose verdict is decided by network latency is a coin
#    flip wearing a gate's clothes, and this file's own header argues against it.
# v3 (this) is OFFLINE. Nothing above this line leaves the machine.
if [ "${SWEEP_PROBE:-}" = "1" ]; then
  echo
  echo "🟢 PROBE — local guards passed, enumeration positive-controlled; no network, no loop"
  exit 0
fi

# ---- what GitHub knows about ------------------------------------------------
PR_REFS="$(gh pr list --state all --limit 1000 --json headRefName --jq '.[].headRefName' 2>/dev/null | sort -u)"
if [ -z "$PR_REFS" ]; then
  echo "🟡 CANNOT TELL — gh returned no PR head refs at all"
  echo "   (this repository has hundreds; an empty answer is the instrument, not the data)"
  exit 2
fi
echo "   · $(printf '%s\n' "$PR_REFS" | grep -c .) distinct PR head refs known to GitHub"
echo

retire=0; wip=0; landed=0; findings=0
FINDING_LIST=""

while IFS= read -r b; do
  [ -n "$b" ] || continue

  state="$(gh pr list --state all --limit 20 --head "$b" --json state --jq '[.[].state] | join(",")' 2>/dev/null)"

  if [ -n "$state" ]; then
    case "$state" in
      *OPEN*)   wip=$((wip+1));    continue ;;
      *MERGED*) retire=$((retire+1))
                echo "   · RETIRE (merged, branch still on origin)  $b"
                continue ;;
    esac
  fi

  # No PR, or only CLOSED-unmerged ones. Does it carry anything main lacks?
  unique="$(git -C "$REPO_DIR" cherry "$BASE" "origin/$b" 2>/dev/null | grep -c '^+')"
  case "$unique" in
    ''|*[!0-9]*) echo "   🟡 CANNOT TELL — git cherry gave '$unique' for $b"; exit 2 ;;
  esac

  if [ "$unique" -eq 0 ]; then
    landed=$((landed+1))
    echo "   · RETIRE (content landed by another route; 0 patch-unique)  $b"
  else
    findings=$((findings+1))
    last="$(git -C "$REPO_DIR" log -1 --format=%cs "origin/$b" 2>/dev/null)"
    FINDING_LIST="$FINDING_LIST   ⚠️  $b — $unique patch-unique commit(s), last $last"$'\n'
  fi
done <<< "$SCOPE"

# ---- reconcile, because a partition that does not add up hides a bucket -----
SUM=$((retire + wip + landed + findings))
if [ "$SUM" -ne "$IN_SCOPE" ]; then
  echo
  echo "🟡 CANNOT TELL — partition does not reconcile: $retire+$wip+$landed+$findings = $SUM, expected $IN_SCOPE"
  exit 2
fi

echo
echo "   in progress (open PR) : $wip"
echo "   merged, not retired   : $retire"
echo "   landed another route  : $landed"
echo "   PUSHED, NEVER LANDED  : $findings"

if [ "$findings" -gt 0 ]; then
  echo
  echo "🔴 $findings BRANCH(ES) CARRY WORK THAT IS NOT IN $BASE AND HAVE NO PR:"
  printf '%s' "$FINDING_LIST"
  echo
  echo "  Each is a decision, not automatically a defect. For each one:"
  echo "    · still wanted  -> open a PR, land it through the gate"
  echo "    · superseded    -> retire it: bash scripts/retire-branch.sh <branch>"
  echo "  Say which in the session report. An unexplained orphan comes back."
  exit 1
fi

echo
echo "🟢 no orphaned work on origin — every in-scope branch is landed, retired-able, or in flight"
exit 0
