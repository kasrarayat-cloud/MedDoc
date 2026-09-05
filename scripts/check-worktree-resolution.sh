#!/usr/bin/env bash
# ============================================================================
# A WORKTREE MUST RESOLVE @meddoc/* TO ITS OWN packages/. READ-ONLY.
# ----------------------------------------------------------------------------
# ⚠️ THE DEFECT THIS PROBES FOR IS SILENT AND IT VOIDS MEASUREMENTS.
# A git worktree has no `node_modules`, so the habit is to symlink the shared
# tree's. Inside it, `@meddoc/auth -> ../../packages/auth` resolves RELATIVE TO
# THE SYMLINK TARGET — i.e. to /opt/meddoc-pro/packages/auth, not the
# worktree's. Every `tsc --noEmit` and every test that IMPORTS a workspace
# package then measures the SHARED tree's code while appearing to measure the
# branch under test.
#
# It produced a clean typecheck and 5,728 passing tests over `packages/auth`
# changes that were never compiled or executed once.
#
# ⚠️ IT FAILS TOWARD "CANNOT TELL" (exit 2) rather than passing. A probe that
# cannot resolve at all must not read as a green.
#
# exit 0 = resolves locally   1 = resolves ELSEWHERE   2 = cannot tell
# ============================================================================
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "🔴 worktree-resolution: not a git tree. CANNOT TELL."; exit 2; }

resolve_from() {
  # $1 = directory to resolve from, $2 = specifier
  node -e '
    const { createRequire } = require("node:module");
    const path = require("node:path");
    try {
      const req = createRequire(path.join(process.argv[1], "package.json"));
      process.stdout.write(require("node:fs").realpathSync(req.resolve(process.argv[2])));
    } catch (e) { process.exit(3); }
  ' "$1" "$2" 2>/dev/null
}

PKGS=$(ls -1 "$ROOT/packages" 2>/dev/null)
[ -n "$PKGS" ] || { echo "🔴 worktree-resolution: no packages/ here. CANNOT TELL."; exit 2; }

# ── POSITIVE CONTROL, FIRST ─────────────────────────────────────────────────
# ⚠️ WITHOUT THIS THE PROBE COULD BE A CONSTANT. Resolve the SAME specifier
# from the SHARED tree and require it to land inside the SHARED tree. If that
# fails, the probe is not tracking the tree it is asked about and no answer it
# gives about this worktree can be believed.
SHARED=/opt/meddoc-pro
if [ "$ROOT" != "$SHARED" ] && [ -d "$SHARED/packages/auth" ]; then
  CTRL=$(resolve_from "$SHARED" "@meddoc/auth")
  case "$CTRL" in
    "$SHARED"/*)
      : ;;
    *)
      echo "🔴 worktree-resolution: POSITIVE CONTROL FAILED."
      echo "   Resolving @meddoc/auth from $SHARED landed at: ${CTRL:-<unresolvable>}"
      echo "   The probe is not tracking the tree it is asked about. CANNOT TELL."
      exit 2 ;;
  esac
fi

rc=0
for p in $PKGS; do
  [ -d "$ROOT/packages/$p" ] || continue
  GOT=$(resolve_from "$ROOT" "@meddoc/$p")
  if [ -z "$GOT" ]; then
    echo "🟡 @meddoc/$p — unresolvable from this tree (not a dependency here?)"
    continue
  fi
  case "$GOT" in
    "$ROOT"/*) echo "🟢 @meddoc/$p -> local" ;;
    *)
      echo "🔴 @meddoc/$p resolves OUTSIDE this worktree:"
      echo "     tree:     $ROOT"
      echo "     resolved: $GOT"
      rc=1 ;;
  esac
done

if [ "$rc" != 0 ]; then
  echo
  echo "   ⚠️ ANY GREEN MEASURED HERE ON A packages/* CHANGE IS VOID."
  echo "   Repair:  bash scripts/setup-worktree.sh \"$ROOT\""
fi
exit "$rc"
