#!/usr/bin/env bash
# ============================================================================
# THE ONLY DOOR TO `prisma generate` — REFUSES WHEN IT WOULD WRITE OUT OF TREE.
# ----------------------------------------------------------------------------
# ⚠️ THIS EXISTS BECAUSE A SESSION RAN `npx prisma generate` IN A WORKTREE AND
# REWROTE THE SHARED CLIENT WHILE A PEER HAD SEVEN TEST PROCESSES RUNNING.
#
# It checked that the worktree's `node_modules` was a real DIRECTORY and not a
# symlink, and concluded the write would be isolated. It was not:
# `node_modules/@prisma` was a symlink, so `@prisma/client` RESOLVED to the
# shared tree and the generator wrote there.
#
#   A REAL DIRECTORY IS NOT AN ISOLATED RESOLUTION.
#   VERIFY THE LOOKUP, NOT THE ARTIFACT.
#
# The generated client is an OUTPUT. Where an output lands is decided by module
# resolution, which is a runtime question no `ls` can answer — so this script
# ASKS NODE where it resolves, and refuses if the answer is outside this tree.
#
# Usage:  bash scripts/prisma-generate.sh [extra prisma args…]
# ============================================================================
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SCHEMA="${PRISMA_SCHEMA:-$ROOT/packages/db/prisma/schema.prisma}"
[ -f "$SCHEMA" ] || { echo "🔴 prisma-generate: no schema at $SCHEMA" >&2; exit 1; }

# ── THE PROBE. Resolve the output path the way NODE will, not the way the
#    filesystem looks. `require.resolve` follows symlinks to the real file, so
#    a linked @prisma/client reports the SHARED path and is caught here.
resolved="$(cd "$ROOT" && node -e '
  try { console.log(require.resolve("@prisma/client")); }
  catch (e) { console.log("UNRESOLVABLE"); }
' 2>/dev/null || echo UNRESOLVABLE)"

if [ "$resolved" = "UNRESOLVABLE" ]; then
  echo "🔴 prisma-generate: cannot resolve @prisma/client from $ROOT." >&2
  echo "   Run: bash scripts/setup-worktree.sh $ROOT" >&2
  exit 1
fi

# ⚠️ FAIL-CLOSED ON CANNOT-TELL. `realpath` both sides before comparing, or a
# symlinked ROOT compares unequal to its own contents and this refuses a
# legitimate run — or worse, a path that merely STARTS WITH the root string
# (/opt/meddoc-pro vs /opt/meddoc-pro-other) passes a naive prefix test.
root_real="$(realpath "$ROOT")"
out_real="$(realpath "$resolved")"
case "$out_real" in
  "$root_real"/*) : ;;
  *)
    echo "🔴 prisma-generate: REFUSING — the generated client would land OUTSIDE this worktree." >&2
    echo "   worktree : $root_real" >&2
    echo "   resolves : $out_real" >&2
    echo >&2
    echo "   `@prisma/client` resolves out of tree, so `prisma generate` would" >&2
    echo "   rewrite a client another worktree — or another SESSION — is using." >&2
    echo "   That happened on 2026-09-07 with seven peer test processes running." >&2
    echo >&2
    echo "   Fix: bash scripts/setup-worktree.sh $ROOT" >&2
    exit 1 ;;
esac

echo "🟢 prisma-generate: output resolves INSIDE this worktree"
echo "   worktree : $root_real"
echo "   resolves : $out_real"
exec npx prisma generate --schema "$SCHEMA" "$@"
