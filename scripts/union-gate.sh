#!/usr/bin/env bash
# ============================================================================
# RUN EVERY PASSENGER'S OWN GATES ON THE MERGED TREE — ruling #184, canon 73.
# ----------------------------------------------------------------------------
# ⚠️ NOTHING A SINGLE BRANCH CAN ASSERT ABOUT ITSELF CATCHES A COLLISION THAT
# EXISTS ONLY IN THE UNION. Each passenger's CI ran on its own branch, against a
# tree that did not contain the other passengers. Git merges cleanly whenever the
# hunks do not overlap textually — which says nothing about whether the combined
# behaviour is still the one each gate was written to protect.
#
# REFERENCE CASE, this deploy: PR #944, PR #948 and PR #962 all edit
# `apps/transcribe-md/src/app/rounds-tokens.css` — 133, 38 and 50 changed lines.
# Three sequential edits to one token file, three green branches, and until this
# script ran nobody had executed all four of their gates against the tree that
# actually ships.
#
# USAGE:  bash scripts/union-gate.sh <base-sha> [<head>]
#         base = the commit production is on; head defaults to HEAD
#
# It finds every test file touched by the range, runs them ALL on the merged
# tree, and prints a declaration row. Exit 0 = union holds; 1 = it does not;
# 2 = cannot tell (which is NOT a pass).
# ============================================================================
set -uo pipefail

BASE="${1:?usage: union-gate.sh <base-sha> [head]}"
HEAD_REF="${2:-HEAD}"

git rev-parse --verify "${BASE}^{commit}" >/dev/null 2>&1 || {
  echo "🔴 union-gate: '$BASE' is not a commit here. CANNOT TELL."; exit 2; }

mapfile -t GATES < <(
  git diff --name-only "$BASE" "$HEAD_REF" -- \
    | grep -E '(__tests__/|\.test\.(ts|tsx)$|\.spec\.(ts|tsx)$)' \
    | grep -v '^apps/transcribe-md/tests/e2e/' \
    | sort -u
)

# ⚠️ POSITIVE CONTROL BEFORE ANY GREEN IS BELIEVED. A range that yields zero
# gate files is either a docs-only deploy or a broken diff, and the two are
# indistinguishable from the exit code alone. Say which.
if [ "${#GATES[@]}" -eq 0 ]; then
  RUNTIME=$(git diff --name-only "$BASE" "$HEAD_REF" | grep -Evc '^(docs/|[^/]+\.md$)')
  if [ "$RUNTIME" -eq 0 ]; then
    echo "🟢 union-gate: 0 gates, 0 runtime files — docs-only range, nothing to union."
    exit 0
  fi
  echo "🔴 union-gate: $RUNTIME runtime files changed and NOT ONE touched a gate."
  echo "   That is a finding, not a pass: a runtime range with no gate movement"
  echo "   means the union is unmeasured. CANNOT TELL."
  exit 2
fi

echo "=== UNION GATE — ${#GATES[@]} gate file(s) from $(git rev-parse --short "$BASE")..$(git rev-parse --short "$HEAD_REF") ==="
printf '  %s\n' "${GATES[@]}"
echo

# Paths are made app-relative for vitest, whose root is the app.
#
# ⚠️ THE FIRST VERSION SILENTLY DROPPED EVERYTHING OUTSIDE THE APP, AND THAT IS
# THE DEFECT THIS WHOLE SCRIPT EXISTS TO PREVENT — one layer inside itself. It
# listed six `packages/ai/**` gates, ran only the twelve under the app, and then
# printed "every passenger's gates pass on the MERGED tree". Six gates belonging
# to the largest passenger in the range were never executed and the row claimed
# they were.
#
# The app's vitest resolves `../../packages/...` fine (measured), so a gate
# outside the app is CONVERTED, never skipped. Anything that cannot be converted
# REFUSES — a union gate that quietly narrows its own watched set is worse than
# no union gate, because it produces a confident row.
APP=apps/transcribe-md
REL=()
DROPPED=()
for g in "${GATES[@]}"; do
  case "$g" in
    "$APP"/*) REL+=("${g#"$APP"/}") ;;
    */*)      REL+=("../../$g") ;;
    *)        DROPPED+=("$g") ;;
  esac
done

if [ "${#DROPPED[@]}" -ne 0 ]; then
  echo "🔴 union-gate: cannot address these gate files from $APP:"
  printf '     %s\n' "${DROPPED[@]}"
  echo "   Refusing to report a union over a set I narrowed. CANNOT TELL."
  exit 2
fi

if [ "${#REL[@]}" -eq 0 ]; then
  echo "🔴 union-gate: no gate file could be addressed. CANNOT TELL."
  exit 2
fi

# ⚠️ ARITHMETIC THAT MUST RECONCILE: every gate found is a gate run.
#
# HONEST NOTE ON THIS CHECK: given the `case` list above it cannot fire, because
# every string matches one of the three arms and DROPPED is already handled. It
# is kept, and it is not dead code, because it is EXACTLY the check that would
# have caught this script's original defect — the version that matched only
# `$APP/*` and silently skipped everything else. Its arm mutates the conversion
# back to that shape and asserts this refusal fires. A ratchet against a
# specific regression, named as such rather than dressed up as a live guard.
if [ "${#REL[@]}" -ne "${#GATES[@]}" ]; then
  echo "🔴 union-gate: found ${#GATES[@]} gate files but addressed ${#REL[@]}."
  echo "   A union over a subset is not a union. CANNOT TELL."
  exit 2
fi

echo "  addressed as:"
printf '    %s\n' "${REL[@]}"
echo

# ⚠️ PLAN-ONLY EXISTS SO THE ADDRESSING LOGIC IS TESTABLE WITHOUT A NODE TREE.
# The defect this script shipped with lived entirely in the conversion above,
# and an arm that cannot reach it is not an arm. It stops BEFORE vitest and
# never reports green, so it can never be mistaken for a passing union.
if [ -n "${UNION_GATE_PLAN_ONLY:-}" ]; then
  echo "🟡 union-gate: PLAN ONLY — ${#GATES[@]} found, ${#REL[@]} addressed, nothing executed."
  exit 0
fi

OUT=$(cd "$APP" && npx vitest run "${REL[@]}" 2>&1)
RC=$?
echo "$OUT" | grep -E '^ +(Tests|Test Files) ' | sed 's/^/  /'

if [ "$RC" -ne 0 ]; then
  echo
  echo "🔴 union-gate: a passenger's own gate FAILS on the merged tree."
  echo "   Each of these passed on its own branch. The union is the finding."
  echo "$OUT" | grep -E '^ +×' | head -20 | sed 's/^/  /'
  exit 1
fi

FILES=$(echo "$OUT" | grep -oE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+')
TESTS=$(echo "$OUT" | grep -E '^ +Tests ' | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+')
echo
echo "🟢 union-gate: every passenger's gates pass on the MERGED tree."
echo "   DECLARATION ROW: union gate — ${#GATES[@]} gate file(s) (all addressed), ${TESTS:-?} tests, green on $(git rev-parse --short "$HEAD_REF")."
echo "   ⚠️ This says the gates hold together. It does NOT say the combined"
echo "      VISUAL or CLINICAL result is right — a gate measures what it measures."
