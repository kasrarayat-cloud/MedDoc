#!/usr/bin/env bash
# ============================================================================
# THE RULED-MUTATION RUNNER — the only door to an irreversible production act.
#   0 = the mutation ran and exited 0   1 = REFUSED (nothing ran)   n = its code
#
#   bash scripts/run-ruled-mutation.sh --declaration <path> -- <command…>
# ----------------------------------------------------------------------------
# WHY
#
# `deploy-prod.sh` has refused to run without a §2.5 declaration since 2026-08-11.
# Ruled MUTATIONS had no such gate: the order lived in a ruling and in whoever
# was executing. That is survivable while a person types the command and it is
# not survivable now that an unattended loop can.
#
# ⚠️ THE REFERENCE CASE IS WHY THE GATE IS STRICTER HERE THAN FOR A DEPLOY.
# B7 step 3c's backfill wrote **175 irreversible rows at 22:50:16Z**, and its
# declaration's only commit is **22:52:13Z** — 1m57s later. All eight declared
# quantities matched exactly and nothing suggests bad faith. **The record simply
# cannot distinguish an honest declaration from one written once the outcome was
# known** — and that distinction was the entire product §2.5 was buying.
#
# So for a mutation the declaration must be COMMITTED before this runs. The act
# has not happened yet, so its commit timestamp provably precedes the rows.
# Nothing else in the record can carry that proof.
#
# The two reference shapes this generalises:
#   · GATE 0.1's `scripts/execute-gate0-deactivation.sql` — owner-ruled, one-shot
#   · B7 step 3c's `apps/transcribe-md/scripts/backfill-promo-grants.ts`
#
# The child is handed two variables so it can refuse to run outside this door:
#   RULED_MUTATION_DECLARATION  path of the committed declaration
#   RULED_MUTATION_DECL_COMMIT  the commit that carries it
# ============================================================================
set -uo pipefail

DECL=""; CMD=()
while [ $# -gt 0 ]; do
  case "$1" in
    --declaration) DECL="${2:-}"; shift 2 ;;
    --declaration=*) DECL="${1#*=}"; shift ;;
    --) shift; CMD=("$@"); break ;;
    *) echo "usage: bash scripts/run-ruled-mutation.sh --declaration <path> -- <command…>"; exit 2 ;;
  esac
done
[ -z "$DECL" ] && { echo "🔴 run-ruled-mutation: --declaration is required."; exit 2; }
[ "${#CMD[@]}" -eq 0 ] && { echo "🔴 run-ruled-mutation: no command given after --."; exit 2; }

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || { echo "🔴 not in a git work tree"; exit 2; }
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/declaration.sh"
[ -r "$LIB" ] || { echo "🔴 run-ruled-mutation: $LIB missing or unreadable. Refusing."; exit 1; }
# shellcheck source=lib/declaration.sh
. "$LIB"

declaration_gate "$DECL" strict "ruled mutation" || exit 1

DECL_COMMIT=$(git log -1 --format=%H -- "$DECL" 2>/dev/null)
DECL_DATE=$(git log -1 --format=%cI -- "$DECL" 2>/dev/null)

# ⚠️ THIS TIMESTAMP IS THE OTHER HALF OF THE PROOF. The declaration's commit time
# and this line bracket the act, in the transcript, in the same units the rows
# carry. A later forensic check compares them without needing anybody's memory.
echo "═══════════════════════════════════════════════════════════════════"
echo "RULED MUTATION — ABOUT TO EXECUTE"
echo "  declaration : $DECL"
echo "  committed   : ${DECL_COMMIT:0:12} at $DECL_DATE"
echo "  command     : ${CMD[*]}"
echo "  starting at : $(date -u +%Y-%m-%dT%H:%M:%SZ)   ← must be AFTER the commit above"
echo "═══════════════════════════════════════════════════════════════════"

export RULED_MUTATION_DECLARATION="$DECL"
export RULED_MUTATION_DECL_COMMIT="$DECL_COMMIT"

"${CMD[@]}"
rc=$?

echo "═══════════════════════════════════════════════════════════════════"
echo "RULED MUTATION — FINISHED at $(date -u +%Y-%m-%dT%H:%M:%SZ), exit $rc"
echo "  declaration : $DECL @ ${DECL_COMMIT:0:12}"
if [ "$rc" -ne 0 ]; then
  echo "  ⚠️ NON-ZERO EXIT. Do not re-run until you know what landed — an"
  echo "     irreversible act that failed partway is not the same as one that"
  echo "     did not run. Verify against the declaration before deciding."
fi
echo "  NEXT: judge the result against the declaration above, every row of it."
echo "═══════════════════════════════════════════════════════════════════"
exit $rc
