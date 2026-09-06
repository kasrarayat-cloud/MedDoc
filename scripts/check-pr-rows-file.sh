#!/usr/bin/env bash
# ============================================================================
# A RUNTIME PR CARRIES ITS §2.5 ROWS FILE. READ-ONLY.
# ----------------------------------------------------------------------------
# The deployer can measure what a change TOUCHES. Only its author can say what
# it is SUPPOSED to do, and therefore what would be a FINDING. Ruling #184 makes
# a passenger without rows a finding rather than a pass; the standing rule puts
# those rows at PR-OPEN time.
#
# ⚠️ IT IS A GATE BECAUSE THE RULE ALONE DID NOT WORK. Twice measured:
#     b54a3b3a   8 passengers, 0 with rows
#     832f8e81   16 passengers, 1 with rows
# The rule was written after the first and had not changed behaviour by the
# second. A rule that does not change what happens becomes mechanism, or it
# becomes a wish.
#
# ⚠️ AND ONE OF THOSE UNROWED PASSENGERS WAS AN IRREVERSIBLE MIGRATION —
# `ALTER TYPE … ADD VALUE`, which Postgres cannot undo. It reached production
# inside another lane's deploy, judged only by rows that lane DERIVED.
#
# EXIT: 0 = rows present or PR is docs-only · 1 = runtime PR with no rows
#       2 = cannot tell (fail-closed; a broken instrument is not a pass)
# ============================================================================
set -uo pipefail

# ⚠️ ANCHORED TO ITS OWN LOCATION, NEVER THE CWD — F28. A granted script that
# resolves repo paths from `pwd` reads whatever tree the caller happened to be
# standing in. That family has bitten this house three times, and the LOUD
# failure (a script that vanishes, exit 127) is the lucky one: the quiet failure
# is a confident answer about a DIFFERENT REAL TREE.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || {
  echo "🔴 rows-gate: cannot resolve repo root from \$BASH_SOURCE."; exit 2; }
cd "$REPO_DIR" || { echo "🔴 rows-gate: cannot enter $REPO_DIR."; exit 2; }

BASE="${1:-origin/main}"
HEAD_REF="${2:-HEAD}"
PR_NUMBER="${PR_NUMBER:-}"

git rev-parse --verify "$BASE" >/dev/null 2>&1 || { echo "🔴 cannot resolve base '$BASE'"; exit 2; }
MB="$(git merge-base "$BASE" "$HEAD_REF" 2>/dev/null)" || { echo "🔴 no merge base"; exit 2; }

# ⚠️ SOURCED, NOT COPIED. `DECLARATION_NONRUNTIME_RE` is the deploy gate's own
# definition of "runtime", and this check must use THAT ONE — a second copy
# drifts from the first the day either is fixed, and what drifts here decides
# whether a change needs rows at all.
#
# ⚠️ I WROTE A SECOND COPY FIRST, hours after recording "one normaliser, two
# callers" as canon from a defect of exactly this shape. The arm caught it.
DECL_LIB="$REPO_DIR/scripts/lib/declaration.sh"
[ -r "$DECL_LIB" ] || { echo "🔴 rows-gate: $DECL_LIB unreadable — cannot tell."; exit 2; }
# shellcheck source=lib/declaration.sh
. "$DECL_LIB"
[ -n "${DECLARATION_NONRUNTIME_RE:-}" ] || {
  echo "🔴 rows-gate: DECLARATION_NONRUNTIME_RE is unset — cannot tell."; exit 2; }
NONRUNTIME_RE="$DECLARATION_NONRUNTIME_RE"

CHANGED="$(git diff --name-only "$MB..$HEAD_REF" 2>/dev/null)" || exit 2
RUNTIME="$(printf '%s\n' "$CHANGED" | grep -vE "$NONRUNTIME_RE" || true)"
N_RUNTIME=$(printf '%s\n' "$RUNTIME" | grep -c . || true)

if [ "$N_RUNTIME" -eq 0 ]; then
  echo "🟢 rows-gate: docs-only ($(printf '%s\n' "$CHANGED" | grep -c .) file(s)) — no rows required."
  exit 0
fi

# rows may arrive in THIS diff, or already exist for this PR number
ROWS_IN_DIFF="$(printf '%s\n' "$CHANGED" | grep -E '^docs/foundation/deploys/rows/PR-[0-9]+\.md$' || true)"
if [ -n "$ROWS_IN_DIFF" ]; then
  echo "🟢 rows-gate: $N_RUNTIME runtime file(s), rows supplied:"
  printf '     %s\n' $ROWS_IN_DIFF
  exit 0
fi

if [ -n "$PR_NUMBER" ] && [ -f "docs/foundation/deploys/rows/PR-${PR_NUMBER}.md" ]; then
  echo "🟢 rows-gate: $N_RUNTIME runtime file(s), rows already tracked at docs/foundation/deploys/rows/PR-${PR_NUMBER}.md"
  exit 0
fi

echo "🔴 rows-gate: $N_RUNTIME RUNTIME FILE(S) AND NO §2.5 ROWS FILE."
printf '     %s\n' $(printf '%s\n' "$RUNTIME" | head -8)
[ "$N_RUNTIME" -gt 8 ] && echo "     … and $((N_RUNTIME - 8)) more"
cat <<'MSG'

   Add docs/foundation/deploys/rows/PR-<n>.md naming, for THIS change:
     · WHAT MUST CHANGE          — with the expected value
     · WHAT MUST NOT CHANGE      — each row with its own falsifier
     · the clinical-count row    — visits / patients / signatures
   A migration additionally names what it does and whether it is reversible.

   ⚠️ Rows are the half a deployer CANNOT supply. They are what makes a
      post-deploy comparison have one correct answer fixed in advance,
      instead of a number with a story available to it.
MSG
exit 1
