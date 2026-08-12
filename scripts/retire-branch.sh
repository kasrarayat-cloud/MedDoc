#!/usr/bin/env bash
# ============================================================================
# Retire a MERGED feature branch — remote first, then local. FAIL-CLOSED.
#   0 = retired (or already gone)   1 = REFUSED   2 = can't tell
#
#   bash scripts/retire-branch.sh <branch>
# ----------------------------------------------------------------------------
# WHY A WRAPPER AND NOT THE GRANT
#
# `git push origin --delete` is in this repo's DENY list, deliberately, beside
# `git push --force`, `git filter-repo`, `git filter-branch`, `git tag -d` and
# `git reset --hard`. That is not an oversight to correct: it is the same verb
# that deletes `main` or a sacred `pre-*` rollback ref, and the branch-cadence
# rule ("retire the branch on merge") needs only a sliver of it.
#
# So the sliver is what gets granted. This script can ONLY delete a branch that
# is already merged into `origin/main`, and refuses protected names outright.
# The general form stays denied.
#
# ⚠️ AND THE HONEST LIMIT, STATED: a deny rule matches the command the agent
# RUNS, not what a script it runs does internally. Any wrapper is therefore a
# hole in that deny by construction — which is exactly why this one has to be
# conservative, and why widening it is a war-room question and not an edit.
#
# ⚠️ ALSO: `gh pr merge --delete-branch` is NOT atomic. It can merge and then
# fail to delete either side, reporting only the local failure. Check, do not
# read its error as "only the local one failed". That is what this script is
# usually cleaning up after.
# ============================================================================
set -uo pipefail

BR="${1:-}"
[ -z "$BR" ] && { echo "usage: bash scripts/retire-branch.sh <branch>"; exit 2; }

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || {
  echo "🟡 retire-branch: not inside a git work tree — can't tell"; exit 2; }

# ── protected names, refused by shape and not by memory ─────────────────────
case "$BR" in
  main|master|HEAD|"") echo "🔴 retire-branch: REFUSED — '$BR' is a trunk ref."; exit 1 ;;
  pre-*|*/pre-*)       echo "🔴 retire-branch: REFUSED — '$BR' looks like a rollback ref."; exit 1 ;;
  refs/*)              echo "🔴 retire-branch: REFUSED — pass a branch NAME, not a full ref."; exit 1 ;;
  -*)                  echo "🔴 retire-branch: REFUSED — '$BR' starts with '-'."; exit 1 ;;
esac
case "$BR" in *' '*|*'*'*|*'?'*|*'..'*)
  echo "🔴 retire-branch: REFUSED — '$BR' contains a wildcard, space or '..'."; exit 1 ;;
esac

git fetch origin --prune -q 2>/dev/null || { echo "🟡 retire-branch: fetch failed — can't tell"; exit 2; }

remote_exists=$(git ls-remote --heads origin "$BR" 2>/dev/null | wc -l)
local_exists=$(git branch --list "$BR" | wc -l)

if [ "$remote_exists" -eq 0 ] && [ "$local_exists" -eq 0 ]; then
  echo "🟢 retire-branch: '$BR' is already gone, both sides. Nothing to do."; exit 0
fi

# ── the gate: it must already be merged into origin/main ────────────────────
if [ "$remote_exists" -gt 0 ]; then
  if ! git merge-base --is-ancestor "origin/$BR" origin/main 2>/dev/null; then
    echo "🔴 retire-branch: REFUSED — 'origin/$BR' is NOT an ancestor of origin/main."
    echo "   It carries commits main does not. Merge it, or delete it by hand and say why."
    echo "   ahead by: $(git rev-list --count origin/main..origin/"$BR" 2>/dev/null) commit(s)"
    exit 1
  fi
  git push origin --delete "$BR" >/dev/null 2>&1
  if [ "$(git ls-remote --heads origin "$BR" 2>/dev/null | wc -l)" -ne 0 ]; then
    echo "🔴 retire-branch: the remote delete did not take — '$BR' is still on origin."; exit 1
  fi
  echo "   · remote  $BR — retired"
fi

# ⚠️ `left` EXISTS BECAUSE THE FIRST VERSION OF THIS SCRIPT PRINTED "🟢 retired"
# AFTER LEAVING THE BRANCH IN PLACE. Caught by its own positive control, not by
# reading it. A script that reports success for work it did not do is the defect
# this repo keeps paying for; the green line is now earned, not unconditional.
left=0
if [ "$local_exists" -gt 0 ]; then
  cur=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ "$cur" = "$BR" ]; then
    echo "🟡 retire-branch: local '$BR' is CHECKED OUT here — left in place. Switch away and re-run."
    left=1
  elif git worktree list --porcelain 2>/dev/null | grep -qx "branch refs/heads/$BR"; then
    echo "🟡 retire-branch: local '$BR' is held by another worktree — left in place."
    left=1
  else
    if git branch -D "$BR" >/dev/null 2>&1; then
      echo "   · local   $BR — deleted"
    else
      echo "🟡 retire-branch: local delete of '$BR' failed."; left=1
    fi
  fi
fi

if [ "$left" -ne 0 ]; then
  echo "🟡 retire-branch: '$BR' is PARTIALLY retired — see above. Not claiming success."
  exit 2
fi

echo "🟢 retire-branch: '$BR' retired."
exit 0
