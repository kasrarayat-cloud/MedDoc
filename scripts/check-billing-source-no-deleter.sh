#!/usr/bin/env bash
# ============================================================================
# `api_usage_events` IS THE BILLING SOURCE. NOTHING MAY DELETE FROM IT.
# ----------------------------------------------------------------------------
# READ-ONLY.  0 = intact · 1 = A DELETER EXISTS · 2 = can't tell
#
# ── WHY THIS TABLE AND NOT THE OTHER ONE — DISCOVERY §C.4, "HOLE 2" ────────
# There are two persistence lanes and, before B2, NEITHER was a correct billing
# source on its own:
#
#   `ai_calls`           held the failed-but-billed tokens — and is HARD-DELETED
#                        by four production paths. Choosing it as the ledger
#                        means A DOCTOR DELETING A VISIT ERASES THEIR OWN BILL.
#   `api_usage_events`   is deleted nowhere — and was missing every failed call,
#                        so choosing it meant silently under-billing ~4% of
#                        Anthropic calls (44 rows, ~$1.53 in production).
#
# B2 closed the second gap by wiring the failure branches that hold
# vendor-reported units. That makes `api_usage_events` the billing source, and
# its no-deleter property STOPS BEING AN ACCIDENT AND BECOMES A REQUIREMENT.
#
# ⚠️ THE PROPERTY WAS ALREADY LOAD-BEARING BEFORE ANYONE WROTE IT DOWN. Ruling
# 77 (2026-08-09) had to state, as a guard note on `runStaleVisitCleanup`, that
# the cleanup "must NEVER touch `api_usage_events`" — an obligation inferred
# from a goal rather than enforced by anything. That sweep already deletes
# `ai_calls` alongside visits and is a no-op today only because trash happens to
# be empty, which is a fact about today. This file is that note turned into a
# check.
#
# ── WHAT IT LOOKS AT, AND WHY THAT UNIVERSE ───────────────────────────────
# A row can leave the table two ways, and a source grep only sees one:
#
#   1. AN EXPLICIT DELETE — ORM (`apiUsageEvent.delete/deleteMany`) or raw SQL.
#   2. A CASCADE — an FK with ON DELETE CASCADE, which removes rows with no
#      code anywhere naming the table. Invisible to every grep ever written.
#
# Both arms run. Arm 2 is the one that would be missed by hand, and it is the
# one a future `@relation(onDelete: Cascade)` on `visitId` would trip.
#
# ⚠️ ARM 1 IS POSITIVE-CONTROLLED, because a zero from a broken grep and a zero
# from a clean tree are the same output. The SAME pattern shape is run against
# `ai_calls`, which is known to have deleters. If that control returns 0 the
# pattern is broken and the script reports 2 (can't tell) rather than a green.
# ============================================================================

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || { echo "🔸 cannot reach repo root"; exit 2; }

FAIL=0
echo "api_usage_events — the billing source. Checking nothing can delete a row."
echo

# ── ARM 1: explicit deleters in the tree ───────────────────────────────────

orm_pattern() { grep -rniE "$1\.(delete|deleteMany)\b" --include=*.ts apps packages scripts 2>/dev/null | grep -v node_modules; }
sql_pattern() { grep -rniE "delete[[:space:]]+from[[:space:]]+\"?$1\b" --include=*.ts --include=*.sql apps packages scripts 2>/dev/null | grep -v node_modules; }

CONTROL=$( { orm_pattern 'aiCall'; sql_pattern 'ai_calls'; } | wc -l )
echo "   positive control — deleters of ai_calls (a table known to have them): ${CONTROL}"
if [ "$CONTROL" -eq 0 ]; then
  echo
  echo "🔸 THE PATTERN FOUND NOTHING WHERE SOMETHING IS KNOWN TO EXIST."
  echo "   The search is broken (shell quoting, a moved directory, a renamed"
  echo "   model). A zero from this script would be meaningless — reporting 2."
  exit 2
fi

HITS=$( { orm_pattern 'apiUsageEvent'; sql_pattern 'api_usage_events'; } )
COUNT=$( [ -z "$HITS" ] && echo 0 || printf '%s\n' "$HITS" | wc -l )

if [ "$COUNT" -eq 0 ]; then
  echo "   ✔ arm 1 — no ORM or raw-SQL deleter of api_usage_events, anywhere"
else
  echo "   ✘ arm 1 — ${COUNT} DELETER(S) OF THE BILLING SOURCE:"
  printf '%s\n' "$HITS" | sed 's/^/       /'
  FAIL=1
fi

# ── ARM 2: cascades, which no grep can see ────────────────────────────────

PSQL_OUT=$(docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tAF'|' -c "
  SELECT conname, confdeltype, pg_get_constraintdef(oid)
  FROM pg_constraint
  WHERE conrelid = 'api_usage_events'::regclass AND contype = 'f'
  ORDER BY conname;" 2>&1)

if [ $? -ne 0 ] || [ -z "$PSQL_OUT" ]; then
  echo "   🔸 arm 2 — cannot reach the database; cascade check UNKNOWN"
  echo
  echo "🔸 can't tell — arm 2 did not run. Not a pass."
  exit 2
fi

echo
echo "   foreign keys on api_usage_events:"
CASCADES=0
while IFS='|' read -r name deltype def; do
  [ -z "$name" ] && continue
  case "$deltype" in
    c) echo "       ✘ ${name} — ON DELETE CASCADE"; CASCADES=$((CASCADES + 1)) ;;
    n) echo "       ✔ ${name} — SET NULL" ;;
    a|r) echo "       ✔ ${name} — NO ACTION / RESTRICT" ;;
    *) echo "       ? ${name} — unrecognised delete rule '${deltype}': ${def}"; CASCADES=$((CASCADES + 1)) ;;
  esac
done <<< "$PSQL_OUT"

if [ "$CASCADES" -gt 0 ]; then
  echo "   ✘ arm 2 — ${CASCADES} FK can remove a billing row by cascade"
  FAIL=1
else
  echo "   ✔ arm 2 — no FK on this table cascades a delete"
fi

# ⚠️ `visitId` deliberately carries NO foreign key. That is what makes deleting
# a visit incapable of touching the meter — the property the four `ai_calls`
# deleters demonstrate the need for. If a future schema change adds
# `@relation(onDelete: Cascade)` there, arm 2 turns red, which is the whole
# point of checking the database rather than the intention.
if printf '%s\n' "$PSQL_OUT" | grep -q 'visitId'; then
  echo "   ⚠ NOTE — a foreign key on visitId now EXISTS. It is not a cascade, or"
  echo "     arm 2 would have failed; but the table has gained a link to a row"
  echo "     that IS routinely deleted. Re-read §C.4 before relying on this."
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "🟢 the billing source is undeletable — no code path and no cascade"
  exit 0
fi
echo "🔴 A BILLING ROW CAN BE DESTROYED. This is revenue, and it does not come back."
exit 1
