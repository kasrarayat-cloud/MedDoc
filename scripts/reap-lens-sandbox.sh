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
# ══════════════════════════════════════════════════════════════════════════════
# ⚠️ AN UNARMED SANDBOX IS REAPABLE — AND UNTIL 2026-09-09 IT WAS NOT.
# ------------------------------------------------------------------------------
# This line used to be an unconditional refusal:
#
#     [ -d "$DIR/.lens-hooks" ] || { echo "carries no .lens-hooks — refusing."; exit 1; }
#
# which refused **exactly the artifact a partial creation leaves behind**: a
# `.lens-*` directory with no hooks in it. So the two scripts composed into a
# self-perpetuating mess — `make` could leave an unarmed sandbox, and `reap`
# was guaranteed to refuse that one and only that one. Measured on this box:
# `.lens-o2-door-offer` had been sitting in the shared tree since an earlier
# session for precisely this reason, and the sanctioned tool could not remove it.
#
# ⚠️ AND `git worktree remove` DOES NOT CLOSE IT EITHER. It removes tracked
# files; an IGNORED artifact keeps the directory alive. `.lens-o2-door-offer`
# held exactly one file — `apps/transcribe-md/node_modules/.vite/vitest/.../
# results.json`, 32K — a vitest cache a lens had written. The worktree
# registration was gone, so `worktree remove` had nothing to act on, and the
# name-based guard below refused the manual path.
#
# ⚠️ A TRAP FOR THE NEXT READER, MET WHILE DIAGNOSING THIS: `git -C <that dir>
# rev-parse HEAD` ANSWERS. It walks UP to the enclosing repository, so an orphan
# directory reports the SHARED tree's HEAD and reads exactly like a live
# worktree. `git worktree list` is the authority for whether it is one.
#
# THE POSTURE IS UNCHANGED — still fail-closed against a mistyped path. The
# name check above (`.lens-*`) and the containment check here are what keep a
# real worktree safe; the hooks check never added safety, only the deadlock.
# ══════════════════════════════════════════════════════════════════════════════
if [ ! -d "$DIR/.lens-hooks" ]; then
  if [ "$(dirname "$DIR")" != "$SHARED" ]; then
    echo "🔴 $DIR carries no .lens-hooks AND is not a direct child of $SHARED — refusing." >&2
    echo "   (an unarmed sandbox is reapable; an arbitrary path is not)" >&2
    exit 1
  fi
  echo "⚠️  $DIR carries no .lens-hooks — UNARMED or orphaned sandbox, reaping it." >&2
fi
git -C "$SHARED" worktree remove --force "$DIR" 2>/dev/null || rm -rf "$DIR"
git -C "$SHARED" worktree prune
echo "🟢 reaped $DIR"
