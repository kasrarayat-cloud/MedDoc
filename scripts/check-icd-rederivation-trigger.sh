#!/usr/bin/env bash
# ============================================================================
# RULING #185 OWES A RE-DERIVATION AFTER 50 REAL DOCTOR DECISIONS.
# NOTHING WAS WATCHING FOR IT. THIS IS THAT WATCHER.
# ----------------------------------------------------------------------------
# READ-ONLY.  0 = not yet owed · 1 = TRIGGER FIRED, re-derivation is DUE · 2 = can't tell
#
# ── WHY THIS EXISTS ────────────────────────────────────────────────────────
# #185 sets the ICD auto-accept threshold at 0.90 and labels it
# SPECIFICATION-DERIVED: it comes from the L7a prompt's own clause
# "0.9 or above = explicit diagnosis statement" — a statement about what the
# model was ASKED to mean, never a measurement of how often it is right. The
# ruling then says: RE-DERIVE AFTER 50 REAL DOCTOR DECISIONS.
#
# The T9 recon (docs/audit-reports/t9-coding-confidence-recon-20260904.md)
# measured ZERO decisions against 58 production visits, so the obligation was
# real and dormant on the same day it was written. A due date nobody watches
# is a wish: "a stated invariant is a WISH until something asserts it."
#
# ── THE NUMBER THAT GATES IS NOT THE OBVIOUS ONE ───────────────────────────
# ⚠️ A RE-DERIVATION NEEDS (confidence, outcome) PAIRS, NOT DECISIONS.
#
# Decisions live in `transcribe_visits.icdDecisions`, an object keyed by CODE:
#   { "<CODE>": { state: accepted|rejected, at, byUserId } }
# Proposals live in `icdCodes -> 'codes'`, each carrying a numeric confidence.
#
# A decision whose code is NO LONGER in that visit's proposals is what
# `lib/icd-decisions.ts` names the `orphaned` bucket. It is a real decision a
# doctor really made — and it CANNOT be paired with a confidence, so it is
# useless as ground truth for a threshold. Counting it toward 50 would fire
# this trigger early and invite a re-derivation on fewer labelled examples
# than the ruling asked for.
#
# So the gating number is PAIRABLE decisions. Total and orphaned are both
# printed, and the partition is asserted to reconcile — per AGENTS.md, "name
# every bucket the scan can sort an item into, and assert the total."
#
# ⚠️ ORPHANS ARE UNREACHABLE TODAY, AND THAT IS NOT A REASON TO SKIP THEM.
# `icdCodes` has one writer and L7a is skipped whenever it has content
# (`worker/layer-skip.ts`), so nothing shipped currently orphans a decision —
# `lib/icd-decisions.ts` says so and keeps the bucket anyway, with its
# re-arming conditions enumerated. A count of 0 here is a POPULATION FACT
# about today, not a property of the code.
#
# ── EVERY ZERO IS THE INSTRUMENT UNTIL PROVEN OTHERWISE ─────────────────────
# A broken query and an untouched product both report "0 decisions". They are
# distinguished by a POSITIVE CONTROL: the count of proposal rows carrying a
# numeric confidence. If that is 0, this script does NOT report "not yet
# owed" — it reports CANNOT TELL, because with no proposals there is nothing
# a decision could even have been made against.
#
# ── ARMS PROVEN, AND THE TWO THAT ARE NOT ──────────────────────────────────
# Proven by execution 2026-09-05:
#   · not-yet-owed      — production, 0 of 50, control 212
#   · classification    — synthetic inputs lifted through this file's OWN SQL:
#                         total 4 / pairable 1 / orphaned 3. Separately covers a
#                         decision on an unproposed code, a NON-NUMERIC
#                         confidence, and a cross-visit match that must NOT pair
#   · TRIGGER FIRED     — QA stack at threshold 3 against 3 real decisions
#   · not fired at 4    — the boundary in the other direction, same data
#   · cannot-tell       — non-numeric threshold · absent container · psql error
#
# ⚠️ NOT PROVEN BY EXECUTION, AND SAID SO RATHER THAN IMPLIED: the control-is-0
# arm and the partition-does-not-reconcile arm. Both need the query to return a
# state no correct query can produce, so reaching them needs either a seeded
# database with every proposal stripped or a test backdoor in this file. A
# backdoor that lets a caller substitute the row is exactly how a check gets
# faked green, so there is not one. What would prove them honestly: a QA
# fixture with proposals removed. Until then they are fail-closed by
# construction and unexercised, which is a weaker statement than the arms above.
#
# ⚠️ IT READS COUNTS, NEVER CONTENT. No quote, description, transcript, note
# or identifier is selected; no per-visit row and no (patient, code) pair is
# printed. Aggregates only — the same posture the T9 recon was run under.
# ============================================================================
set -uo pipefail

THRESHOLD="${ICD_REDERIVATION_THRESHOLD:-50}"
PG_CONTAINER="${PG_CONTAINER:-meddoc-pro-postgres-1}"
PG_USER="${PG_USER:-meddoc}"
PG_DB="${PG_DB:-meddoc}"

case "$THRESHOLD" in
  ''|*[!0-9]*) echo "🟡 CANNOT TELL — threshold '$THRESHOLD' is not a number"; exit 2 ;;
esac

if ! docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
  echo "🟡 CANNOT TELL — no container '$PG_CONTAINER' (run this on the host that owns production)"
  exit 2
fi

ROW="$(docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -X -tA -F'|' -v ON_ERROR_STOP=1 <<'SQL' 2>/dev/null
WITH dec AS (
  SELECT vv.id AS vid, k AS code
  FROM (
    SELECT id, "icdDecisions"::jsonb AS j
    FROM transcribe_visits
    WHERE "icdDecisions" IS NOT NULL
      AND jsonb_typeof("icdDecisions"::jsonb) = 'object'
  ) vv
  CROSS JOIN LATERAL jsonb_object_keys(vv.j) k
),
prop AS (
  SELECT vv.id AS vid, e->>'code' AS code
  FROM (
    SELECT id, "icdCodes"::jsonb AS j
    FROM transcribe_visits
    WHERE "icdCodes" IS NOT NULL
      AND jsonb_typeof("icdCodes"::jsonb -> 'codes') = 'array'
  ) vv
  CROSS JOIN LATERAL jsonb_array_elements(vv.j -> 'codes') e
  WHERE jsonb_typeof(e -> 'confidence') = 'number'
)
SELECT
  (SELECT count(*) FROM dec),
  (SELECT count(*) FROM dec d WHERE EXISTS (SELECT 1 FROM prop p WHERE p.vid = d.vid AND p.code = d.code)),
  (SELECT count(*) FROM dec d WHERE NOT EXISTS (SELECT 1 FROM prop p WHERE p.vid = d.vid AND p.code = d.code)),
  (SELECT count(*) FROM prop);
SQL
)"

if [ -z "$ROW" ]; then
  echo "🟡 CANNOT TELL — the query returned nothing (psql error, or the columns moved)"
  exit 2
fi

IFS='|' read -r TOTAL PAIRABLE ORPHANED CONTROL <<< "$ROW"

for v in "$TOTAL" "$PAIRABLE" "$ORPHANED" "$CONTROL"; do
  case "$v" in
    ''|*[!0-9]*) echo "🟡 CANNOT TELL — non-numeric value in result row: '$ROW'"; exit 2 ;;
  esac
done

# ⚠️ NEVER NORMALISE AN IMPOSSIBLE VALUE. If the partition does not reconcile,
# the instrument is wrong and no verdict it produces is worth reading.
if [ "$((PAIRABLE + ORPHANED))" -ne "$TOTAL" ]; then
  echo "🟡 CANNOT TELL — partition does not reconcile: pairable $PAIRABLE + orphaned $ORPHANED != total $TOTAL"
  exit 2
fi

# The positive control. A zero here means the question cannot be asked, not
# that the answer is "no".
if [ "$CONTROL" -eq 0 ]; then
  echo "🟡 CANNOT TELL — positive control is 0: no proposal row carries a numeric confidence."
  echo "   With no proposals there is nothing a decision could have been made against,"
  echo "   so a decision count of $TOTAL cannot be interpreted. Check the shape of icdCodes."
  exit 2
fi

echo "   ruling #185 — re-derive the 0.90 threshold after $THRESHOLD real doctor decisions"
echo "   positive control — proposal rows with a numeric confidence: $CONTROL"
echo "   decisions recorded (all)            : $TOTAL"
echo "   ├─ PAIRABLE with a confidence       : $PAIRABLE   <- this is the number that gates"
echo "   └─ orphaned (code no longer proposed): $ORPHANED   <- real, but unusable as ground truth"

if [ "$PAIRABLE" -ge "$THRESHOLD" ]; then
  cat <<MSG
🔴 TRIGGER FIRED — the re-derivation ruling #185 owes is now DUE.

  $PAIRABLE pairable decisions >= $THRESHOLD.

  What is owed is a MEASUREMENT, not a re-reading of the specification:
  join each decision to its proposal's confidence and report how often the
  model was right at and around 0.90. Until that is done the threshold stays
  SPECIFICATION-DERIVED, and 0.80 stays refused by name (#185).

  The T9 recon is the instrument and the format:
    docs/audit-reports/t9-coding-confidence-recon-20260904.md
MSG
  exit 1
fi

echo "🟢 not yet owed — $PAIRABLE of $THRESHOLD pairable decisions"
exit 0
