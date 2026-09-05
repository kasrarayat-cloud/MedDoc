#!/usr/bin/env bash
# ============================================================================
# Give a git worktree a SELF-CONSISTENT node_modules. Run once per worktree.
# ----------------------------------------------------------------------------
# Mirrors the shared tree's installed dependencies by symlink (cheap, no
# network, no lockfile risk) and then OVERRIDES @meddoc/* to point at THIS
# worktree's own packages/ — which is the whole point. See
# `scripts/check-worktree-resolution.sh` for why the naive whole-directory
# symlink silently measures the wrong tree.
# ============================================================================
set -euo pipefail
SHARED=/opt/meddoc-pro
TARGET="${1:-$(git rev-parse --show-toplevel)}"
TARGET="$(cd "$TARGET" && pwd)"

[ "$TARGET" != "$SHARED" ] || { echo "🔴 setup-worktree: refusing to rewrite the SHARED tree's node_modules."; exit 1; }
[ -d "$TARGET/packages" ] || { echo "🔴 setup-worktree: $TARGET has no packages/."; exit 1; }

link_tree() {  # $1 = source node_modules, $2 = destination
  local src="$1" dst="$2"
  [ -d "$src" ] || return 0
  [ -L "$dst" ] && rm "$dst"          # a SYMLINK only; never the target
  mkdir -p "$dst"
  local n=0
  for e in "$src"/* "$src"/.bin; do
    [ -e "$e" ] || continue
    local b; b="$(basename "$e")"
    [ "$b" = "@meddoc" ] && continue
    ln -sfn "$e" "$dst/$b" && n=$((n+1))
  done
  echo "   linked $n entries into ${dst#$TARGET/}"
}

link_tree "$SHARED/node_modules" "$TARGET/node_modules"
mkdir -p "$TARGET/node_modules/@meddoc"
for pkg in "$TARGET"/packages/*; do
  [ -d "$pkg" ] || continue
  ln -sfn "$pkg" "$TARGET/node_modules/@meddoc/$(basename "$pkg")"
done
echo "   @meddoc/* -> $TARGET/packages/*  (LOCAL)"

for app in "$TARGET"/apps/*; do
  [ -d "$app" ] || continue
  link_tree "$SHARED/apps/$(basename "$app")/node_modules" "$app/node_modules"
done

echo
# ⚠️ THE CHECKER IS INVOKED FROM THIS SCRIPT'S OWN DIRECTORY, NOT FROM $TARGET.
# A worktree being repaired is often on a branch that PREDATES this harness, so
# `$TARGET/scripts/check-worktree-resolution.sh` may not exist there — and the
# repair would then end with "No such file" instead of a verdict.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
( cd "$TARGET" && bash "$HERE/check-worktree-resolution.sh" )
