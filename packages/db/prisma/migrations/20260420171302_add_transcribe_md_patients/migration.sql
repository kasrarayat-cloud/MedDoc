-- T-M17.2 Phase 1: TranscribeMD-scoped Patient model.
-- See schema.prisma `model TranscribeMdPatient` for the rationale and
-- why this is a separate table from the CRM `patients` table.

-- pg_trgm backs the fuzzy-match endpoint and the dashboard search box.
-- IF NOT EXISTS keeps the migration idempotent across environments
-- (e.g. CI or a local reset where the extension is already there).
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Main table
CREATE TABLE "transcribe_md_patients" (
    "id"          TEXT NOT NULL,
    "practiceId"  TEXT NOT NULL,
    "name"        TEXT NOT NULL,
    "dateOfBirth" DATE,
    "externalId"  TEXT,
    "deletedAt"   TIMESTAMPTZ(6),
    "createdAt"   TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"   TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "transcribe_md_patients_pkey" PRIMARY KEY ("id")
);

-- FK to practices. ON DELETE CASCADE so the T-M16.2 delete-account flow
-- (which drops the solo user's synthetic Practice last) sweeps the
-- patient rows as part of that transaction. Visits are already gone by
-- that point (cascaded from User.delete), so the cascade chain doesn't
-- trip the transcribe_visits → transcribe_md_patients RESTRICT below.
ALTER TABLE "transcribe_md_patients"
    ADD CONSTRAINT "transcribe_md_patients_practiceId_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON UPDATE CASCADE ON DELETE CASCADE;

-- Filtered list queries (`WHERE practiceId = $1 AND deletedAt IS NULL`)
-- are the hot path for the dashboard + patient picker.
CREATE INDEX "transcribe_md_patients_practiceId_deletedAt_idx"
    ON "transcribe_md_patients"("practiceId", "deletedAt");

-- Trigram GIN index — powers the fuzzy-match endpoint via
-- `similarity(LOWER(name), LOWER($1)) > 0.4`. LOWER() is baked in so
-- the index still applies after case folding.
CREATE INDEX "transcribe_md_patients_name_trgm_idx"
    ON "transcribe_md_patients"
    USING GIN (LOWER("name") gin_trgm_ops);

-- Link visits to patients. Nullable here; Phase 1 Commit 3 tightens to
-- NOT NULL after the backfill script runs.
ALTER TABLE "transcribe_visits" ADD COLUMN "patientId" TEXT;

-- RESTRICT on delete so hard-deleting a patient while visits exist
-- fails fast. Soft delete via deletedAt is the expected path.
ALTER TABLE "transcribe_visits"
    ADD CONSTRAINT "transcribe_visits_patientId_fkey"
    FOREIGN KEY ("patientId") REFERENCES "transcribe_md_patients"("id")
    ON UPDATE CASCADE ON DELETE RESTRICT;

CREATE INDEX "transcribe_visits_patientId_idx"
    ON "transcribe_visits"("patientId");
