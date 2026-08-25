#!/usr/bin/env bash
# ============================================================================
# Assert this clone's git hooks are LIVE. READ-ONLY.
#   0 = installed and executable   1 = NOT live (a FINDING)   2 = can't tell
# ----------------------------------------------------------------------------
# WHY: hooks do NOT travel with a clone. `core.hooksPath` is set by the root
# `prepare` script on `npm install`, which means a fresh clone that has not
# installed — or a session whose config was reset — carries the hook FILES and
# runs none of them. Nothing anywhere would say so.
#
# "A stated invariant is a WISH until something asserts it." The pre-commit
# clinical-document guard and the pre-push in-flight-runs guard are both worth
# exactly as much as this check.
#
# ⚠️ THE CENSUS ARM IS NOT DECORATION. A hand-kept list of hooks goes stale the
# first time somebody adds one, so this compares what is PRESENT in the hooks
# directory against what is REQUIRED, and reports either direction: a required
# hook missing is a finding, and a present-but-not-executable hook is a finding
# whether or not anybody listed it.
# ============================================================================
set -uo pipefail

REQUIRED=(pre-commit pre-push)
HOOKS_DIR=scripts/hooks

# ⚠️ F28: RESOLVE THE ROOT FROM THIS SCRIPT'S OWN LOCATION, NEVER FROM THE CWD.
# The previous form was `cd "$(git rev-parse --show-toplevel)"`, which anchors to
# whatever tree the CALLER happens to be standing in. Run from a worktree, it
# checked THAT worktree's scripts/hooks and printed a green that was true about
# a tree nobody deploys — while `core.hooksPath` is repo-level and shared, so the
# two halves of the comparison could come from two different trees.
# A persisted `cd` then produces a confident WRONG answer instead of a loud one.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || {
  echo "🟡 check-hooks-installed: cannot resolve this script's own root — can't tell"; exit 2; }
cd "$ROOT" || {
  echo "🟡 check-hooks-installed: cannot enter $ROOT — can't tell"; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || {
  echo "🟡 check-hooks-installed: $ROOT is not inside a git work tree — can't tell"; exit 2; }

configured=$(git config --get core.hooksPath 2>/dev/null || true)
if [ -z "$configured" ]; then
  echo "🔴 check-hooks-installed: core.hooksPath is UNSET — every hook in $HOOKS_DIR is inert."
  echo "   Fix: npm install   (or: git config core.hooksPath $HOOKS_DIR)"
  exit 1
fi
if [ "$configured" != "$HOOKS_DIR" ]; then
  echo "🔴 check-hooks-installed: core.hooksPath is '$configured', expected '$HOOKS_DIR'."
  exit 1
fi

fail=0
for h in "${REQUIRED[@]}"; do
  p="$configured/$h"
  if [ ! -f "$p" ]; then echo "🔴 required hook MISSING: $p"; fail=1; continue; fi
  if [ ! -x "$p" ]; then echo "🔴 required hook NOT EXECUTABLE: $p"; fail=1; continue; fi
  if ! bash -n "$p" 2>/dev/null; then echo "🔴 required hook has a SYNTAX ERROR: $p"; fail=1; continue; fi
  echo "   · $h — present, executable, parses"
done

# census: anything present that is not executable is a finding too
while IFS= read -r p; do
  [ -z "$p" ] && continue
  base=$(basename "$p")
  case " ${REQUIRED[*]} " in *" $base "*) continue ;; esac
  if [ ! -x "$p" ]; then echo "🔴 unlisted hook present but NOT EXECUTABLE: $p"; fail=1
  else echo "   · $base — present (not in the required set), executable"; fi
done < <(find "$configured" -maxdepth 1 -type f 2>/dev/null)

[ "$fail" -ne 0 ] && exit 1
echo "🟢 check-hooks-installed: core.hooksPath=$configured, ${#REQUIRED[@]} required hooks live."
exit 0
