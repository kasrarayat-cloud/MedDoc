#!/usr/bin/env bash
# ============================================================================
# EVERY WORKTREE, WITH ITS MERGE STATE — because IGNORED IS NOT ACCOUNTED-FOR.
# ----------------------------------------------------------------------------
# READ-ONLY. Exits 0 always; this reports, it never reaps.
#
# ⚠️ THE PAIRING IS THE POINT. `.gitignore` hides worktree directories so they
# cannot block the loop's launch guard, which counts UNTRACKED files and refuses
# to start. That fix creates its own blind spot: `.f5i2-queue` sat attached to a
# branch that had already MERGED, invisible to `git status` precisely because the
# ignore rule was working. A shield is also a blindfold.
#
# So the ignore pattern ships WITH this listing, and the listing names the one
# fact that decides whether a worktree should still exist: is its branch merged?
# ============================================================================
set -uo pipefail
# ⚠️ THE SHARED TREE IS FOUND VIA --git-common-dir, NOT --show-toplevel.
# `--show-toplevel` answers about the tree the script is RUNNING IN, so the first
# version of this script — run from a worktree — labelled that worktree "the
# shared tree" and labelled /opt/meddoc-pro "REAPABLE". It would have told
# somebody to delete a DEPLOY SURFACE. A tree-relative instrument answers about
# its own tree; the common dir is the same for every worktree of a repo.
COMMON="$(git rev-parse --git-common-dir 2>/dev/null)" || { echo "not a git repo"; exit 0; }
case "$COMMON" in /*) ;; *) COMMON="$(cd "$COMMON" && pwd)";; esac
MAIN_WT="$(dirname "$COMMON")"
cd "$MAIN_WT" || { echo "cannot reach the shared tree"; exit 0; }
git fetch origin --quiet 2>/dev/null || true

printf '%-52s %-38s %s\n' "WORKTREE" "BRANCH" "STATE"
printf '%-52s %-38s %s\n' "--------" "------" "-----"

n=0; reapable=0
while IFS= read -r line; do
  case "$line" in worktree\ *) wt="${line#worktree }";; *) continue;; esac
  n=$((n+1))
  br="$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  if [ "$wt" = "$MAIN_WT" ]; then
    state="the shared tree — never reap"
  elif [ "$br" = "HEAD" ]; then
    state="detached — inspect by hand"
  elif ! git rev-parse --verify -q "origin/$br" >/dev/null 2>&1; then
    # no remote branch: either merged+retired, or never pushed. Distinguish.
    if [ -n "$(git -C "$wt" log --oneline "origin/main..$br" 2>/dev/null)" ]; then
      state="⚠️ UNPUSHED COMMITS — do not reap"
    else
      state="✅ REAPABLE — remote branch gone, nothing unpushed"; reapable=$((reapable+1))
    fi
  elif git merge-base --is-ancestor "$br" origin/main 2>/dev/null; then
    state="✅ REAPABLE — merged into main"; reapable=$((reapable+1))
  else
    dirty="$(git -C "$wt" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    state="open work (${dirty} uncommitted)"
  fi
  printf '%-52s %-38s %s\n' "$wt" "$br" "$state"
done < <(git worktree list --porcelain)

echo
echo "$n worktree(s); $reapable reapable."
[ "$reapable" -gt 0 ] && echo "⚠️ A reapable worktree is invisible to \`git status\` by design — that is what this listing is for."
exit 0
