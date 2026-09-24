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

# ── PRISMA GETS REAL DIRECTORIES, NOT SYMLINKS. ─────────────────────────────
# ⚠️ THIS EXISTS BECAUSE THE LINK-EVERYTHING RULE ABOVE HAS ONE EXCEPTION IT DID
# NOT KNOW ABOUT, AND A SESSION WROTE THROUGH IT INTO THE SHARED TREE WHILE A
# PEER HAD SEVEN TEST PROCESSES RUNNING.
#
#   · `@prisma/client` symlinked to the shared tree means `prisma generate`
#     RESOLVES there and writes there — the generated client is an OUTPUT, and
#     an output must never be a symlink into somebody else's directory.
#   · `.prisma` was not linked AT ALL: `link_tree` iterates `"$src"/*`, and a
#     glob does not match a leading dot. So the worktree had no generated client
#     of its own and silently used the shared one.
#
# The session that hit this checked that `node_modules` was a real DIRECTORY and
# concluded it was isolated. It was not: a real directory is not an isolated
# RESOLUTION. Only these two are copied (~91 MB); the rest of `@prisma`
# (engines, ~23 MB) stays linked because nothing writes to it.
prisma_real() {
  local nm="$TARGET/node_modules"
  [ -d "$SHARED/node_modules/@prisma" ] || return 0

  # @prisma/ becomes a real directory: everything linked EXCEPT client, copied.
  [ -L "$nm/@prisma" ] && rm "$nm/@prisma"
  mkdir -p "$nm/@prisma"
  for e in "$SHARED"/node_modules/@prisma/*; do
    [ -e "$e" ] || continue
    local b; b="$(basename "$e")"
    [ "$b" = "client" ] && continue
    ln -sfn "$e" "$nm/@prisma/$b"
  done
  rm -rf "$nm/@prisma/client"
  cp -a "$SHARED/node_modules/@prisma/client" "$nm/@prisma/client"

  # .prisma/ — the GENERATED client. Always real, never linked.
  [ -L "$nm/.prisma" ] && rm "$nm/.prisma"
  rm -rf "$nm/.prisma"
  if [ -d "$SHARED/node_modules/.prisma" ]; then
    cp -a "$SHARED/node_modules/.prisma" "$nm/.prisma"
  else
    mkdir -p "$nm/.prisma"
  fi
  echo "   @prisma/client and .prisma -> REAL directories in this worktree"
}
prisma_real

# ── rebuild/.venv: THE SHARED VENV, LINKED ONCE AND VALIDATED (2026-09-24). ──
# A second plain `ln -s` onto an existing directory link writes INSIDE the target: it planted `.venv/.venv` in the
# shared production venv, and the activation's readability gate refused an install 18 hours later. The pre-push hook
# needs this link, so it is made here, by the one script that reuses a correct link and refuses anything else.
if [ -d "$TARGET/rebuild" ]; then
  bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/link-worktree-venv.sh" "$TARGET"
fi

echo
# ⚠️ THE CHECKER IS INVOKED FROM THIS SCRIPT'S OWN DIRECTORY, NOT FROM $TARGET.
# A worktree being repaired is often on a branch that PREDATES this harness, so
# `$TARGET/scripts/check-worktree-resolution.sh` may not exist there — and the
# repair would then end with "No such file" instead of a verdict.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
( cd "$TARGET" && bash "$HERE/check-worktree-resolution.sh" )
