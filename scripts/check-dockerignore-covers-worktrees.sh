#!/usr/bin/env bash
# ============================================================================
# EVERY GIT WORKTREE AT THE CONTEXT ROOT IS EXCLUDED FROM THE BUILD CONTEXT.
# ----------------------------------------------------------------------------
#   0 = every root worktree is covered
#   1 = at least one is NOT covered  (a FINDING — it ships into every build)
#   2 = cannot tell
#
# WHY THIS IS A SCRIPT AND NOT A COMMENT. `.dockerignore` carries a STATIC list
# of worktree name families, and worktree names are ad hoc — the next one may
# be `.wt-991` (covered) or `.recon-b3` (not). A static list without a check is
# a fix with a decay date, and the decay is silent: the build still succeeds,
# it just quietly ships another 155 MB.
#
# ⚠️ IT IS DELIBERATELY HOST-SIDE, NOT CI. A CI checkout has no worktrees, so a
# CI arm here would be VACUOUS — green forever while the real context grows.
# This runs where worktrees actually exist.
set -uo pipefail

# ⚠️ RESOLVE THE **MAIN** WORKING TREE, NOT THIS SCRIPT'S OWN. The build context
# is always `/opt/meddoc-pro` — the shared tree — and this script is also copied
# into every feature worktree. Resolved relative to itself, it would `cd` into a
# WORKTREE, find no worktrees nested under that, and report a confident green
# about a directory nobody builds from. A tree-relative instrument answers about
# ITS OWN tree; the question here is about a different one.
#
# `--git-common-dir` points at the shared `.git` for every worktree, so its
# parent IS the main working tree from wherever this runs.
COMMON="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
  || { echo "🟡 dockerignore-worktrees: not a git tree — cannot tell"; exit 2; }
ROOT="$(dirname "$COMMON")"
[ -d "$ROOT" ] || { echo "🟡 cannot resolve the main working tree — cannot tell"; exit 2; }
cd "$ROOT" || { echo "🟡 cannot enter $ROOT"; exit 2; }
[ -f .dockerignore ] || { echo "🟡 no .dockerignore at $ROOT — cannot tell"; exit 2; }

mapfile -t PATTERNS < <(grep -vE '^\s*#|^\s*$|^!' .dockerignore)
[ "${#PATTERNS[@]}" -gt 0 ] || { echo "🟡 .dockerignore has no rules — cannot tell"; exit 2; }

mapfile -t WORKTREES < <(
  git worktree list --porcelain 2>/dev/null \
    | awk -v r="$ROOT/" '/^worktree /{p=$2; if (index(p,r)==1){ rest=substr(p,length(r)+1); if (rest !~ /\//) print rest }}'
)

# ⚠️ POSITIVE CONTROL. An empty worktree list and a broken `git worktree list`
# produce the same silence, and one of them means "all clear".
if [ "${#WORKTREES[@]}" -eq 0 ]; then
  if git worktree list >/dev/null 2>&1; then
    echo "🟢 dockerignore-worktrees: no worktrees at the context root — nothing to cover."
    exit 0
  fi
  echo "🟡 dockerignore-worktrees: 'git worktree list' failed — cannot tell."; exit 2
fi

covered=0; uncovered=()
for w in "${WORKTREES[@]}"; do
  hit=0
  for p in "${PATTERNS[@]}"; do
    p="${p%/}"
    # shellcheck disable=SC2254
    case "$w" in $p) hit=1; break ;; esac
  done
  if [ "$hit" -eq 1 ]; then covered=$((covered+1)); else uncovered+=("$w"); fi
done

echo "  root worktrees: ${#WORKTREES[@]}  covered: $covered  uncovered: ${#uncovered[@]}"
if [ "${#uncovered[@]}" -ne 0 ]; then
  echo "🔴 dockerignore-worktrees: these SHIP into every build context:"
  for w in "${uncovered[@]}"; do
    echo "     $w   ($(du -sh "$w" 2>/dev/null | cut -f1))"
  done
  echo "   Add a matching line to .dockerignore. Each one costs its own size on"
  echo "   EVERY build stage that uses the repo root as context."
  exit 1
fi
echo "🟢 dockerignore-worktrees: all ${#WORKTREES[@]} root worktrees are excluded."
