-- ===========================================================================
-- GATE 0.1 EXECUTION — deactivate the 12 MEDDOC_PRO-only accounts.
-- ---------------------------------------------------------------------------
-- RULING: GATE 0.1 (SPEC §4.1), veto LAPSED and owner-confirmed 2026-08-05.
--   "Excluded from backfill, DEACTIVATED, rows retained, NO DELETION."
--
-- ⚠️ THIS MUTATES PRODUCTION USER ROWS. It is authorised by that ruling and by
-- nothing else. It never deletes, never touches a clinical row, and it aborts
-- rather than guessing if the population is not exactly what was ruled on.
--
-- ⚠️ THE CLASSIFIER IS RE-RUN HERE, NOT COPIED FROM THE DOCUMENT.
-- SPEC §4.2: "the query is 'does this user own any transcribe_visits /
-- transcribe_md_patients row', and it must be run at migration time, not copied
-- from this document." A user who acquired clinical data since the ruling is a
-- DIFFERENT case and must stop this script, not ride it.
--
-- ⚠️ REACTIVATION IS ALREADY GUARDED. T6's CHECK
-- `users_active_member_has_practice_role` constrains ACTIVE members only, so
-- deactivating is legal; and these rows KEEP their practiceRole, so the
-- reactivation path (which restores OWNER only where practice-and-no-role)
-- leaves them exactly as they were. Verified before writing this file.
--
-- Run:  psql -v ON_ERROR_STOP=1 -f scripts/execute-gate0-deactivation.sql
-- ===========================================================================

BEGIN;

DO $$
DECLARE
  target      int;
  with_data   int;
  already_off int;
BEGIN
  SELECT count(*) INTO target
    FROM users u
   WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
     AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[]);

  -- ⚠️ THE RULING NAMED TWELVE. A different number means the population moved
  -- since the veto was answered, and this script has no authority over the
  -- difference.
  IF target <> 12 THEN
    RAISE EXCEPTION 'GATE 0.1 named 12 MEDDOC_PRO-only accounts; found %. Refusing — the ruling does not cover this population.', target;
  END IF;

  -- The classifier, re-run. A row that acquired clinical data is not the row
  -- that was ruled on.
  SELECT count(*) INTO with_data
    FROM users u
   WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
     AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[])
     AND (EXISTS (SELECT 1 FROM transcribe_visits v WHERE v."userId" = u.id)
       OR EXISTS (SELECT 1 FROM transcribe_md_patients p WHERE p."practiceId" = u."practiceId"));

  IF with_data > 0 THEN
    RAISE EXCEPTION '% of the 12 now own clinical data. GATE 0.2 classifies by WHERE CLINICAL DATA LIVES — these are normal backfill users, not deactivation candidates. Refusing.', with_data;
  END IF;

  SELECT count(*) INTO already_off
    FROM users u
   WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
     AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[])
     AND u."isActive" = false;

  RAISE NOTICE '[gate0] target=% with_clinical_data=% already_deactivated=%', target, with_data, already_off;
END $$;

-- The deactivation. Rows are RETAINED — no delete, no anonymisation.
UPDATE users u
   SET "isActive"      = false,
       "deactivatedAt" = now(),
       "deactivatedBy" = 'gate0-ruling-2026-08-05'
 WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
   AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[])
   AND u."isActive" = true;

-- One audit row per account. §164.312(b): the deactivation is an access-affecting
-- administrative act and must be attributable to the ruling that authorised it.
INSERT INTO audit_logs (id, action, "targetType", "targetId", metadata, "timestamp", "practiceIdSnapshot")
SELECT
  'gate0-' || substr(md5(u.id || '-gate0-deactivation'), 1, 20),
  'USER_DEACTIVATED'::"AuditAction",
  'User',
  u.id,
  jsonb_build_object(
    'ruling', 'GATE 0.1 (SPEC §4.1) — veto lapsed, owner-confirmed 2026-08-05',
    'reason', 'MEDDOC_PRO-only account; excluded from the TEAMS backfill',
    'rowsRetained', true,
    'clinicalDataOwned', false
  ),
  now(),
  u."practiceId"
FROM users u
WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
  AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[]);

-- ⚠️ VERIFY BEFORE COMMITTING. A partial deactivation that reported success is
-- the failure mode this whole file is shaped against.
DO $$
DECLARE
  still_active int;
  audited      int;
BEGIN
  SELECT count(*) INTO still_active
    FROM users u
   WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
     AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[])
     AND u."isActive" = true;

  SELECT count(*) INTO audited
    FROM audit_logs
   WHERE action = 'USER_DEACTIVATED'::"AuditAction"
     AND metadata->>'ruling' LIKE 'GATE 0.1%';

  IF still_active > 0 THEN
    RAISE EXCEPTION '[gate0] % accounts are still active after the update. Rolling back.', still_active;
  END IF;
  IF audited <> 12 THEN
    RAISE EXCEPTION '[gate0] % audit rows written, expected 12. Rolling back — a deactivation without its trail is not done.', audited;
  END IF;

  RAISE NOTICE '[gate0] 12 deactivated, 12 audit rows, 0 still active, 0 rows deleted';
END $$;

COMMIT;
