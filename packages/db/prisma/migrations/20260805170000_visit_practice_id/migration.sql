-- ============================================================================
-- T3 — practiceId on transcribe_visits, with the derivation stated.
-- ----------------------------------------------------------------------------
-- DERIVATION: patient.practiceId. NOT user.practiceId.
--
-- ⚠️ RATIFIED AS A WAR-ROOM RULING, 2026-08-05. This is no longer one
-- migration's choice — it is the project's rule for what a note belongs to:
--   * THE CHART OWNS THE NOTE.
--   * The locum case is the discriminator: a doctor from practice B seeing a
--     patient of practice A creates a note in A.
--   * The composite FK is the enforcement, not a convention anyone must recall.
-- Any future column, query or export that needs "which practice is this visit"
-- derives it the same way. Changing it is a war-room decision, not a refactor.
--
-- Both agreed on all 26 production rows when this was written (measured
-- 2026-08-05: 26 visits, 26 agree, 0 disagree, no nulls). Nothing in the
-- database kept them agreeing, which is exactly why the choice had to be made
-- deliberately rather than inherited from whichever join was handy.
--
-- WHY THE PATIENT:
--   * A note belongs to the practice that owns the CHART. If a locum from
--     practice B sees a patient of practice A, the note belongs in A. Deriving
--     from the author would file it in B and split that patient's history
--     across tenants — silently, and irreversibly by the time anyone noticed.
--   * `transcribe_md_patients.practiceId` is ALREADY the tenancy anchor.
--     Deriving from the patient keeps ONE source of truth. Deriving from the
--     user creates a SECOND, independent one, and two sources that nothing
--     reconciles is the drift this column exists to end.
--
-- ⚠️ THE CONSTRAINT IS A COMPOSITE FK, NOT A TRIGGER, AND THAT IS THE POINT.
-- A trigger can be disabled, bypassed by a bulk load, or forgotten in a
-- restore. A composite FK makes a cross-practice visit UNREPRESENTABLE: there
-- is no (id, practiceId) pair to point at. The gate's "proven by attempting
-- one" then fails at the storage layer rather than at application code that
-- someone could route around.
-- ============================================================================

-- 1. The FK target. A composite FK needs a UNIQUE on exactly these columns.
--    (id is already the PK, so this is redundant for uniqueness and required
--    for referenceability — Postgres will not accept a composite FK without it.)
ALTER TABLE "transcribe_md_patients"
  ADD CONSTRAINT "transcribe_md_patients_id_practiceId_key" UNIQUE ("id", "practiceId");

-- 2. Nullable first, so the backfill has somewhere to land.
ALTER TABLE "transcribe_visits" ADD COLUMN "practiceId" TEXT;

-- 3. Backfill from the PATIENT, per the derivation above.
UPDATE "transcribe_visits" v
   SET "practiceId" = p."practiceId"
  FROM "transcribe_md_patients" p
 WHERE p.id = v."patientId"
   AND v."practiceId" IS NULL;

-- 4. FAIL THE MIGRATION if anything is still unset. A partially-backfilled
--    column that then takes NOT NULL is a migration that half-ran and reported
--    success — the failure mode this project has met before.
DO $$
DECLARE unset int;
BEGIN
  SELECT count(*) INTO unset FROM "transcribe_visits" WHERE "practiceId" IS NULL;
  IF unset > 0 THEN
    RAISE EXCEPTION 'T3 ABORT: % visits still have a NULL practiceId after backfill', unset;
  END IF;
END $$;

-- 5. Now it can be NOT NULL.
ALTER TABLE "transcribe_visits" ALTER COLUMN "practiceId" SET NOT NULL;

-- 6. The composite FK. THIS is what makes a cross-practice visit impossible.
--    ON UPDATE CASCADE mirrors the existing patientId FK; ON DELETE RESTRICT
--    likewise — a practice cannot be deleted out from under a visit.
ALTER TABLE "transcribe_visits"
  ADD CONSTRAINT "transcribe_visits_patientId_practiceId_fkey"
  FOREIGN KEY ("patientId", "practiceId")
  REFERENCES "transcribe_md_patients"("id", "practiceId")
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- 7. The scoping index every practice-filtered query will want.
CREATE INDEX "transcribe_visits_practiceId_idx" ON "transcribe_visits"("practiceId");
