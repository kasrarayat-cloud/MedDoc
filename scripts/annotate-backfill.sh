#!/usr/bin/env bash
# ============================================================================
# THE ANNOTATION BACKFILL — rulings #155(b) and R1's recovery clause.
# ----------------------------------------------------------------------------
# APPEND-ONLY. Writes 39 audit rows across 38 visits and touches NOTHING else:
# no visit row, no fill manifest, no document byte. #155(a) ruled that the ten
# already-signed records STAY AS SIGNED — the freeze is this product's deepest
# promise — so the gap is made VISIBLE rather than repaired.
#
#   dry run (default):  bash scripts/annotate-backfill.sh
#   apply:              bash scripts/annotate-backfill.sh --apply
#
# ⚠️ IDEMPOTENT BY CONSTRUCTION. Each INSERT is guarded by NOT EXISTS on
# (action, targetId), so a second run writes zero rows. An append-only table has
# no undo; "run it twice by accident" must not be able to double the record.
#
# ⚠️ THE IDs ARE UUIDs WHILE THE APP WRITES cuids, AND THAT IS A CHOICE, NOT AN
# OVERSIGHT. Every application-written row carries a cuid (`cmtdqn5a5000h01sd…`);
# these carry `gen_random_uuid()`. Measured before deciding: audit_logs has ZERO
# inbound foreign keys and ZERO check constraints, so nothing can break on the
# difference — and a backfilled row being distinguishable at a glance is a
# property worth having in an append-only trail. The `retrospective: true`
# metadata is the authoritative marker; the id shape is a second, weaker one.
#
# ⚠️ THE 29 NEVER CARRY AN INFERRED TEMPLATE ID. The old `ON DELETE SET NULL`
# destroyed the binding and NO deletion audit row was ever written — measured:
# `audit_logs` holds 9 template-targeted rows and every one is TEMPLATE_TWIN_*,
# none a deletion. So the original id is genuinely unrecoverable, and the metadata
# says exactly that rather than guessing a plausible one.
# ============================================================================
set -uo pipefail
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
PSQL=(docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc -v ON_ERROR_STOP=1)

q() { "${PSQL[@]}" -t -A -c "$1" 2>/dev/null; }

BEFORE=$(q "SELECT count(*) FROM audit_logs;")
P10=$(q "SELECT count(*) FROM transcribe_visits WHERE \"cptCodes\"->'em'='null'::jsonb AND \"emScoredCode\" IS NOT NULL AND \"signedAt\" IS NOT NULL;")
P29=$(q "SELECT count(*) FROM transcribe_visits WHERE \"noteTemplateId\" IS NULL AND status NOT IN ('FAILED','QUEUED');")
OVERLAP=$(q "SELECT count(*) FROM transcribe_visits WHERE \"cptCodes\"->'em'='null'::jsonb AND \"emScoredCode\" IS NOT NULL AND \"signedAt\" IS NOT NULL AND \"noteTemplateId\" IS NULL AND status NOT IN ('FAILED','QUEUED');")

echo "  audit_logs before      : $BEFORE"
echo "  #155(b) population     : $P10   (expect 10)"
echo "  R1 population          : $P29   (expect 29)"
echo "  overlap                : $OVERLAP    (expect 1 — that visit gets TWO rows, two facts)"
echo "  rows to write          : $((P10+P29))  across $((P10+P29-OVERLAP)) distinct visits"

# ⚠️ THE GUARD FIRES BEFORE ANY WRITE. A population that has moved since the
# declaration means the declaration describes a different world.
if [ "$P10" != "10" ] || [ "$P29" != "29" ] || [ "$OVERLAP" != "1" ]; then
  echo "🔴 REFUSING — a population moved since the declaration (10/29/1 expected)."
  echo "   Nothing was written. Re-measure, re-declare, then run."
  exit 1
fi

if [ "$APPLY" != "1" ]; then
  echo "  DRY RUN — nothing written. Re-run with --apply."
  exit 0
fi

"${PSQL[@]}" <<'SQL'
BEGIN;

-- #155(b): one row per SIGNED visit whose artifact printed no E/M.
-- References #152/#879's forward fix. The visit row is NOT touched.
INSERT INTO audit_logs (id, action, "targetId", "targetType", "userId", "practiceId",
                        success, metadata, "timestamp")
SELECT gen_random_uuid()::text, 'EM_OMITTED_IN_SIGNED_ARTIFACT', v.id, 'transcribe_visit',
       v."userId", v."practiceId", true,
       jsonb_build_object(
         'retrospective', true,
         'ruling', '#155(b)',
         'forwardFix', '#152 / PR #879',
         'measuredAt', now(),
         'signedAt', v."signedAt",
         'emScoredCode', v."emScoredCode",
         'note', 'The screen showed an E/M level; the signed artifact carried none. '
              || 'The record STAYS AS SIGNED per #155(a) — this row makes the gap '
              || 'visible without moving a byte.'),
       now()
FROM transcribe_visits v
WHERE v."cptCodes"->'em' = 'null'::jsonb AND v."emScoredCode" IS NOT NULL AND v."signedAt" IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM audit_logs a
                  WHERE a.action = 'EM_OMITTED_IN_SIGNED_ARTIFACT' AND a."targetId" = v.id);

-- R1: one row per servable visit whose template binding was destroyed.
-- ⚠️ NO INFERRED TEMPLATE ID. It is not recoverable and the row says so.
INSERT INTO audit_logs (id, action, "targetId", "targetType", "userId", "practiceId",
                        success, metadata, "timestamp")
SELECT gen_random_uuid()::text, 'TEMPLATE_PROVENANCE_LOST', v.id, 'transcribe_visit',
       v."userId", v."practiceId", true,
       jsonb_build_object(
         'retrospective', true,
         'ruling', 'R1 recovery clause',
         'cause', 'FK ON DELETE SET NULL on transcribe_visits.noteTemplateId, since fixed to RESTRICT',
         'measuredAt', now(),
         'destructionWindow', '2026-07-07..2026-08-27 (updatedAt range of the affected set)',
         'originalTemplate', 'not identifiable — no deletion audit row was ever written',
         'note', 'This visit still SERVES; its provenance does not. The fence prevents '
              || 'new loss and repairs none of this.'),
       now()
FROM transcribe_visits v
WHERE v."noteTemplateId" IS NULL AND v.status NOT IN ('FAILED','QUEUED')
  AND NOT EXISTS (SELECT 1 FROM audit_logs a
                  WHERE a.action = 'TEMPLATE_PROVENANCE_LOST' AND a."targetId" = v.id);

COMMIT;
SQL
rc=$?

AFTER=$(q "SELECT count(*) FROM audit_logs;")
echo "  audit_logs after       : $AFTER   (delta $((AFTER-BEFORE)), expect 39)"
# ⚠️ THE VISIT TABLE MUST BE UNTOUCHED — the whole point of #155(a).
echo "  visits/signed unchanged: $(q "SELECT count(*)||'/'||count(*) FILTER (WHERE \"signedAt\" IS NOT NULL) FROM transcribe_visits;")"
# ⚠️ ASSERT THE END STATE, NOT THE TRANSITION. The first version required a
# delta of exactly 39 — which is right on the first run and WRONG on every
# idempotent re-run, where the correct delta is 0. It printed a red for correct
# behaviour, and a false red teaches people to ignore reds. The invariant that
# holds on BOTH runs is the final count: 10 + 29 rows exist, no more, no fewer.
EM=$(q "SELECT count(*) FROM audit_logs WHERE action::text='EM_OMITTED_IN_SIGNED_ARTIFACT';")
PV=$(q "SELECT count(*) FROM audit_logs WHERE action::text='TEMPLATE_PROVENANCE_LOST';")
VIS=$(q "SELECT count(DISTINCT \"targetId\") FROM audit_logs WHERE action::text IN ('EM_OMITTED_IN_SIGNED_ARTIFACT','TEMPLATE_PROVENANCE_LOST');")
echo "  end state: EM_OMITTED=$EM (want 10) · PROVENANCE_LOST=$PV (want 29) · distinct visits=$VIS (want 38)"
if [ "$rc" = "0" ] && [ "$EM" = "10" ] && [ "$PV" = "29" ] && [ "$VIS" = "38" ]; then
  if [ "$((AFTER-BEFORE))" = "0" ]; then
    echo "  ✅ already applied — idempotent re-run wrote nothing, end state correct"
  else
    echo "  ✅ $((AFTER-BEFORE)) rows appended, end state correct, nothing else moved"
  fi
else
  echo "  🔴 END STATE WRONG — investigate before re-running"
fi
exit 0
