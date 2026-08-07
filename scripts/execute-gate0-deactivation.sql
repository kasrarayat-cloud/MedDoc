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

-- ⚠️ THE NO-DELETION PROOF PINS ITS OWN BASELINE, INSIDE THE TRANSACTION.
-- An earlier draft hardcoded `196`. That is a number copied from a document,
-- and it goes stale the moment somebody signs up — the same "derive it, never
-- thread it" rule T3's raw-SQL sites take. Captured here, compared at the end.
CREATE TEMP TABLE _gate0_baseline ON COMMIT DROP AS
  SELECT count(*)::int AS users_before FROM users;

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
--
-- ⚠️ BOTH `practiceId` AND `practiceIdSnapshot` ARE SET, AND THE OMISSION OF THE
-- FIRST WAS A REAL DEFECT — corrected 2026-08-07 before this ever ran.
-- Under T2's fail-closed rule a NULL `practiceId` MEANS SOMETHING: "this row's
-- tenant could not be resolved". Measured on production, 10546 of 10560 rows
-- carry both; only 8 are snapshot-only and 6 are system rows with neither. These
-- twelve are trivially resolvable — `u."practiceId"` is already in this SELECT —
-- so writing the snapshot alone would have filed twelve perfectly-attributable
-- rows into the bucket reserved for attribution FAILURES, and quietly eroded the
-- one signal T2 exists to make trustworthy. Nothing would have errored.
--
-- `userId` stays NULL deliberately: the actor here is a war-room RULING, not a
-- logged-in human, and inventing a user to satisfy the column would be a false
-- claim about who acted. The `ruling` key in `metadata` is the attribution.
INSERT INTO audit_logs (id, action, "targetType", "targetId", metadata, "timestamp", "practiceId", "practiceIdSnapshot")
SELECT
  'gate0-' || substr(md5(u.id || '-gate0-deactivation'), 1, 20),
  'USER_DEACTIVATED'::"AuditAction",
  'User',
  u.id,
  jsonb_build_object(
    'ruling', 'GATE 0.1 (SPEC §4.1) — veto lapsed, owner-confirmed 2026-08-05',
    'reason', 'MEDDOC_PRO-only account; excluded from the TEAMS backfill',
    'rowsRetained', true,
    'clinicalDataOwned', false,
    'actor', 'ruling — no session user; see SPEC §4.1'
  ),
  now(),
  u."practiceId",
  u."practiceId"
FROM users u
WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
  AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[]);

-- ⚠️ VERIFY BEFORE COMMITTING. A partial deactivation that reported success is
-- the failure mode this whole file is shaped against.
DO $$
DECLARE
  still_active   int;
  audited        int;
  unattributed   int;
  deactivated    int;
  users_total    int;
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

  -- ⚠️ THE ROW COUNT IS NOT THE CLAIM. "12 audit rows exist" is satisfied by 12
  -- rows that say nothing useful; the claim is that each one is ATTRIBUTED.
  SELECT count(*) INTO unattributed
    FROM audit_logs
   WHERE metadata->>'ruling' LIKE 'GATE 0.1%'
     AND ("practiceId" IS NULL OR "practiceIdSnapshot" IS NULL OR "targetId" IS NULL);

  SELECT count(*) INTO deactivated
    FROM users u
   WHERE u.products @> ARRAY['MEDDOC_PRO']::"Product"[]
     AND NOT (u.products && ARRAY['TRANSCRIBE_MD']::"Product"[])
     AND u."isActive" = false;

  SELECT users_before INTO users_total FROM _gate0_baseline;

  IF still_active > 0 THEN
    RAISE EXCEPTION '[gate0] % accounts are still active after the update. Rolling back.', still_active;
  END IF;
  IF audited <> 12 THEN
    RAISE EXCEPTION '[gate0] % audit rows written, expected 12. Rolling back — a deactivation without its trail is not done.', audited;
  END IF;
  IF unattributed > 0 THEN
    RAISE EXCEPTION '[gate0] % audit rows are missing practiceId/snapshot/targetId. Rolling back — an unattributed audit row is the state T2 exists to prevent.', unattributed;
  END IF;
  IF deactivated <> 12 THEN
    RAISE EXCEPTION '[gate0] % deactivated, expected 12. Rolling back.', deactivated;
  END IF;
  -- NO DELETION. The ruling says rows are retained; prove it rather than assert it.
  IF (SELECT count(*) FROM users) <> users_total THEN
    RAISE EXCEPTION '[gate0] users total moved % → % — a row was created or DELETED. Rolling back.',
      users_total, (SELECT count(*) FROM users);
  END IF;

  RAISE NOTICE '[gate0] 12 deactivated · 12 audit rows, all attributed · 0 still active · users % → %, 0 deleted',
    users_total, (SELECT count(*) FROM users);
END $$;

COMMIT;
