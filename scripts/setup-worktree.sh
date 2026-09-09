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

# ⚠️ RULING #282 — THE MIRROR REFUSES A REAL-DIRECTORY DESTINATION, NAMING IT.
#
# `ln -sfn SRC DST` does NOT replace DST when DST is a REAL DIRECTORY. It puts
# the link INSIDE it, as `DST/$(basename SRC)` — and `-f` makes it overwrite
# whatever was already there under that name. `-n` does not help: it only stops
# dereferencing a symlink-to-directory, and a real directory is not one.
#
# ⚠️ MEASURED, ON A WORKTREE THAT ALREADY HAD A REAL `npm install`: **680
# packages** received a self-nested `pkg/pkg -> /shared/node_modules/pkg` link,
# and for `decimal.js` — a package whose own main file shares the package's name
# — the link OVERWROTE THE REAL FILE. The tree then failed with
# `Cannot find module '.../decimal.js/decimal.js'`, and the vitest pool could not
# start at all.
#
# ⚠️ AND IT PRINTED `🟢 linked N entries` THE WHOLE TIME. `n` counted `ln`
# invocations that returned 0, which every one of those did — they succeeded at
# creating a link in the wrong place. That is the *"a script that prints a number
# it does not act on"* family, with the number counting intentions.
#
# The old line only ever removed a SYMLINK destination (`[ -L "$dst" ] && rm`),
# which is the one case that was already safe. A real directory is the dangerous
# one and it was the one left standing.
link_tree() {  # $1 = source node_modules, $2 = destination
  local src="$1" dst="$2"
  [ -d "$src" ] || return 0
  [ -L "$dst" ] && rm "$dst"          # a SYMLINK only; never the target
  mkdir -p "$dst"
  local n=0 refused=0
  for e in "$src"/* "$src"/.bin; do
    [ -e "$e" ] || continue
    local b; b="$(basename "$e")"
    [ "$b" = "@meddoc" ] && continue
    # ⚠️ THE REFUSAL, AND IT NAMES THE PATH. A destination that is a real
    # directory (not a symlink to one) would swallow the link instead of being
    # replaced by it, so the mirror does not guess — it stops and says which.
    if [ -d "$dst/$b" ] && [ ! -L "$dst/$b" ]; then
      if [ "$refused" -eq 0 ]; then
        echo "🔴 setup-worktree: REFUSING — the destination already holds REAL directories." >&2
        echo "   \`ln -sfn\` would nest the link INSIDE each one and report success," >&2
        echo "   and with -f it overwrites any file of the same name. That is how a" >&2
        echo "   tree with a real \`npm install\` lost 680 packages and its decimal.js." >&2
        echo "   Remove the directory and re-run, or use the tree as it is:" >&2
      fi
      refused=$((refused + 1))
      [ "$refused" -le 5 ] && echo "     $dst/$b" >&2
      continue
    fi
    ln -sfn "$e" "$dst/$b" && n=$((n+1))
  done
  if [ "$refused" -gt 0 ]; then
    echo "   ... and $((refused > 5 ? refused - 5 : 0)) more" >&2
    echo "🔴 setup-worktree: $refused real-directory destination(s); nothing further was linked into ${dst#$TARGET/}." >&2
    return 1
  fi
  echo "   linked $n entries into ${dst#$TARGET/}"
}

link_tree "$SHARED/node_modules" "$TARGET/node_modules" || {
  echo "🔴 setup-worktree: STOPPING. The tree was NOT made runnable, and nothing" >&2
  echo "   further was linked — a half-mirrored tree resolves @meddoc/* to the" >&2
  echo "   SHARED tree, so a green in it can be a green about another tree's code." >&2
  exit 1
}
mkdir -p "$TARGET/node_modules/@meddoc"
for pkg in "$TARGET"/packages/*; do
  [ -d "$pkg" ] || continue
  ln -sfn "$pkg" "$TARGET/node_modules/@meddoc/$(basename "$pkg")"
done
echo "   @meddoc/* -> $TARGET/packages/*  (LOCAL)"

for app in "$TARGET"/apps/*; do
  [ -d "$app" ] || continue
  link_tree "$SHARED/apps/$(basename "$app")/node_modules" "$app/node_modules" || {
    echo "🔴 setup-worktree: STOPPING at $app — see above." >&2
    exit 1
  }
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

echo
# ⚠️ THE CHECKER IS INVOKED FROM THIS SCRIPT'S OWN DIRECTORY, NOT FROM $TARGET.
# A worktree being repaired is often on a branch that PREDATES this harness, so
# `$TARGET/scripts/check-worktree-resolution.sh` may not exist there — and the
# repair would then end with "No such file" instead of a verdict.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
( cd "$TARGET" && bash "$HERE/check-worktree-resolution.sh" )
