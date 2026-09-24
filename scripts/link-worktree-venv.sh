#!/usr/bin/env bash
# ============================================================================
# Link a worktree's rebuild/.venv to the SHARED venv — idempotent, validated.
#   0 = linked, or already linked correctly (nothing written)   1 = refused
# ----------------------------------------------------------------------------
# ⚠️ WHY THIS EXISTS. `ln -s <venv> rebuild/.venv` run a second time, when that
# path is already a link to the venv, does not fail: ln treats the existing
# DIRECTORY link as the destination directory and writes the new link INSIDE
# it. On 2026-09-23 that planted `/opt/meddoc-pro/rebuild/.venv/.venv` (a loop
# back to the venv) in the SHARED production venv. Nothing noticed for 18 hours,
# until the activation driver's source-readability gate — which walks the live
# application tree as an unrelated UID and allows exactly four venv links —
# refused an install rehearsal.
#
# So: an existing correct link is REUSED (nothing written); a link pointing
# anywhere else, or a real file or directory, is REFUSED; a new link is made
# with `ln -T`, which never writes inside an existing directory; and the shared
# venv itself is checked for any link the activation gate would refuse.
# ============================================================================
set -euo pipefail

SHARED_VENV="${QUILLMD_SHARED_VENV:-/opt/meddoc-pro/rebuild/.venv}"
[ "$#" -eq 1 ] || { echo "usage: link-worktree-venv.sh <worktree>"; exit 1; }
TARGET="$(cd "$1" && pwd -P)"
LINK="$TARGET/rebuild/.venv"

[ -d "$TARGET/rebuild" ] || { echo "🔴 link-worktree-venv: $TARGET has no rebuild/."; exit 1; }
[ -d "$SHARED_VENV" ] && [ ! -L "$SHARED_VENV" ] || {
  echo "🔴 link-worktree-venv: the shared venv $SHARED_VENV is not a real directory."; exit 1; }
[ "$(cd "$TARGET/rebuild" && pwd -P)" != "$(cd "$(dirname "$SHARED_VENV")" && pwd -P)" ] || {
  echo "🔴 link-worktree-venv: $TARGET is the shared tree; its venv is not a link."; exit 1; }

if [ -L "$LINK" ]; then
  [ "$(readlink "$LINK")" = "$SHARED_VENV" ] || {
    echo "🔴 link-worktree-venv: rebuild/.venv points to $(readlink "$LINK"), not $SHARED_VENV; refusing."; exit 1; }
  echo "   rebuild/.venv -> $SHARED_VENV (already linked; reused, nothing written)"
elif [ -e "$LINK" ]; then
  echo "🔴 link-worktree-venv: rebuild/.venv exists and is not a link; refusing to replace it."; exit 1
else
  ln -sT "$SHARED_VENV" "$LINK"
  echo "   rebuild/.venv -> $SHARED_VENV (linked)"
fi

# The shared venv may hold only the links the activation readability gate allows.
extra="$(find "$SHARED_VENV" -type l ! -path "$SHARED_VENV/lib64" ! -path "$SHARED_VENV/bin/python" \
          ! -path "$SHARED_VENV/bin/python3" ! -path "$SHARED_VENV/bin/python3.12" -print)"
if [ -n "$extra" ]; then
  echo "🔴 link-worktree-venv: unexpected symlink(s) inside the shared venv (the activation gate refuses them):"
  printf '     %s\n' $extra
  echo "   Inspect each with stat/readlink (never follow it) and unlink only the accidental one."
  exit 1
fi
