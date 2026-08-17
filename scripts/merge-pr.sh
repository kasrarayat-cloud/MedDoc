#!/usr/bin/env bash
# ============================================================================
# Merge a PR without destroying somebody's in-flight citation. FAIL-CLOSED.
#   0 = merged   1 = REFUSED or the merge did not take   2 = can't tell
#
#   bash scripts/merge-pr.sh <pr-number> [--merge|--squash|--rebase]
# ----------------------------------------------------------------------------
# WHY THIS EXISTS — AND WHY THE PRE-PUSH HOOK DOES NOT COVER IT
#
# `gh pr merge` merges SERVER-SIDE. It never invokes a client-side git hook, so
# `scripts/hooks/pre-push` — which closes the PUSH-side class — cannot see a
# merge at all. AGENTS.md has TWO sections here for a reason, and the merge side
# has the worse record:
#
#   · 2026-08-08  merging one PR 17 minutes after another left a 3-of-4 citation
#                 on a DEPLOYED commit
#   · 2026-08-10  three pairs merged ~4 seconds apart; one killed a run at
#                 33m39s that another session was deliberately waiting for
#   · 2026-08-12  a supervised merge forced the loop into a RELAY.md conflict
#
# ⚠️ THE 2026-08-10 CASE IS THE ARGUMENT: the waiting party had taken both views,
# seen the runs, and correctly chosen to wait. The rule was followed by one actor
# and defeated by another. That is why this has to be a MERGE-side control and
# not only a push-side one.
#
# The check itself lives in `scripts/lib/inflight.sh` and is shared with the
# hook — one implementation, two doors.
#
# ⚠️ THE SAME HONEST LIMIT AS `retire-branch.sh`: a deny matches the command the
# agent RUNS, not what a script it runs does internally, so this wrapper is a
# hole in the `gh pr merge` deny by construction. It is conservative on purpose,
# and widening it is a war-room question rather than an edit.
#
# The declared-batch override is the legitimate path AGENTS.md already names:
#
#     DECLARE_CANCELLATION="merging #618 and #619 as one declared batch; the
#     cancelled e2e is mine" bash scripts/merge-pr.sh 619
# ============================================================================
set -uo pipefail

PR="${1:-}"
METHOD="${2:---merge}"
case "$PR" in ''|*[!0-9]*) echo "usage: bash scripts/merge-pr.sh <pr-number> [--merge|--squash|--rebase]"; exit 2 ;; esac
case "$METHOD" in --merge|--squash|--rebase) ;; *) echo "🔴 merge-pr: unknown method '$METHOD'"; exit 2 ;; esac

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || { echo "🟡 merge-pr: not in a git work tree — can't tell"; exit 2; }
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/inflight.sh"
[ -r "$LIB" ] || { echo "🟡 merge-pr: $LIB missing or unreadable — can't tell"; exit 2; }
# shellcheck source=lib/inflight.sh
. "$LIB"

DECL="${DECLARE_CANCELLATION:-}"
inflight_declaration_ok "$DECL" || { echo "🔴 merge-pr: (DECLARE_CANCELLATION)"; exit 1; }
inflight_require_gh              || { echo "🟡 merge-pr: refusing."; exit 2; }
inflight_positive_control        || { echo "🟡 merge-pr: refusing."; exit 2; }

state=$(gh pr view "$PR" --json state --jq .state 2>/dev/null)
[ -z "$state" ] && { echo "🟡 merge-pr: cannot read PR #$PR — can't tell"; exit 2; }
if [ "$state" != "OPEN" ]; then
  echo "🔴 merge-pr: PR #$PR is $state, not OPEN. Nothing merged."; exit 1
fi

# ⚠️ THE BASE IS READ FROM THE PR, NEVER ASSUMED TO BE main. A PR onto a release
# branch would otherwise be checked against the wrong ref's runs — the
# right question asked of the wrong universe.
base=$(gh pr view "$PR" --json baseRefName --jq .baseRefName 2>/dev/null)
[ -z "$base" ] && { echo "🟡 merge-pr: cannot read the base branch — can't tell"; exit 2; }
git fetch origin "$base" -q 2>/dev/null || { echo "🟡 merge-pr: fetch of '$base' failed — can't tell"; exit 2; }
base_sha=$(git rev-parse "origin/$base" 2>/dev/null)

inflight_count "$base" "$base_sha" || { echo "🟡 merge-pr: refusing."; exit 2; }
busy=$(inflight_total)

# ⚠️ SAME ANNOUNCEMENT AS THE PUSH DOOR, AND IT MATTERS MORE HERE. Since F14-b a
# repo-wide `/actions/runs` outage no longer blinds this wrapper — `runs-api.sh`
# unions the per-workflow route instead. The commit half of the count keeps its
# check-suites coverage control in that mode; the BRANCH half has none, so its
# zero is a FLOOR. A merge is irreversible in a way a push is not, so the
# degradation is printed whether the verdict is "clear" or "refused".
if [ "${INFLIGHT_DEGRADED:-0}" = "1" ]; then
  echo "🟡 merge-pr: ${INFLIGHT_NOTE}" >&2
  echo "             $base @ ${base_sha:0:8} — --commit $INFLIGHT_BY_COMMIT, --branch $INFLIGHT_BY_BRANCH" >&2
fi

if [ "$busy" -gt 0 ]; then
  if [ -z "$DECL" ]; then
    {
      echo ""
      echo "🔴 merge-pr REFUSED — merging #$PR would cancel runs in flight on '$base'."
      echo ""
      echo "    · $base @ ${base_sha:0:8} — in flight: --commit $INFLIGHT_BY_COMMIT, --branch $INFLIGHT_BY_BRANCH"
      echo ""
      echo "  A merge IS a push. Those runs are somebody's citation, and GitHub"
      echo "  cancels them the moment this merge lands."
      echo ""
      echo "  WAIT for them, or declare the batch:"
      echo ""
      echo "      DECLARE_CANCELLATION=\"why this is deliberate\" bash scripts/merge-pr.sh $PR"
      echo ""
    } >&2
    exit 1
  fi
  {
    echo "═══════════════════════════════════════════════════════════════════"
    echo "DECLARED CANCELLATION — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "  merging  : PR #$PR into $base"
    echo "  cancels  : $base @ ${base_sha:0:8} — --commit $INFLIGHT_BY_COMMIT, --branch $INFLIGHT_BY_BRANCH"
    echo "  reason   : $DECL"
    echo "═══════════════════════════════════════════════════════════════════"
  } >&2
fi

gh pr merge "$PR" "$METHOD" >/dev/null 2>&1
rc=$?

# ⚠️ THE EXIT CODE IS NOT THE EVIDENCE — `gh pr merge --delete-branch` is already
# on record as reporting one failure while silently leaving another. Re-read the
# PR and only claim success if it actually says MERGED.
after=$(gh pr view "$PR" --json state,mergeCommit --jq '"\(.state) \(.mergeCommit.oid // "-")"' 2>/dev/null)
st=${after%% *}; oid=${after##* }
if [ "$st" != "MERGED" ]; then
  echo "🔴 merge-pr: PR #$PR is '$st' after the attempt (gh exit $rc) — NOT merged."
  echo "   Not claiming a success that did not happen. Check required checks and conflicts."
  exit 1
fi

echo "🟢 merge-pr: PR #$PR merged into $base as ${oid:0:8}"
echo "   next: bash scripts/retire-branch.sh <branch>   (--delete-branch is not atomic)"
exit 0
