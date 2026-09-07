#!/usr/bin/env bash
# Remove a lens sandbox and its worktree registration. Refuses anything that is
# not a lens sandbox, so a mistyped argument cannot eat a real worktree.
set -euo pipefail
# ⚠️ THE ROOT IS DERIVED, NOT HARDCODED — AND THIS SESSION FIXED THE SAME BUG
# ONE HOUR EARLIER IN #1009. A literal `/opt/meddoc-pro` is correct on this VPS
# and does not exist on the CI runner or in any worktree, so a check written
# that way passes locally and is meaningless (or red) everywhere else.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED="$(git -C "$HERE" rev-parse --show-toplevel)"
DIR="${1:?usage: reap-lens-sandbox.sh <dir>}"
DIR="$(cd "$DIR" && pwd)"
case "$(basename "$DIR")" in
  .lens-*) : ;;
  *) echo "🔴 $DIR is not a lens sandbox (name must start with .lens-)." >&2; exit 1 ;;
esac
[ -d "$DIR/.lens-hooks" ] || { echo "🔴 $DIR carries no .lens-hooks — refusing." >&2; exit 1; }
git -C "$SHARED" worktree remove --force "$DIR" 2>/dev/null || rm -rf "$DIR"
git -C "$SHARED" worktree prune
echo "🟢 reaped $DIR"
