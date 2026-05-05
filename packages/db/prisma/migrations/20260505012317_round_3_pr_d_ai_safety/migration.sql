-- Round 3 PR-D — AI safety deterministic backstops.
-- Closes audit findings A06-P0-001 (empty-transcript guard),
--                       A06-P0-002 (ICD-10 + CPT allowlist),
--                       A06-P0-004 (clinical-pharmacology backstop, partial).
--
-- Each new AuditAction value is consumed by a deterministic guard added
-- in PR-D. Mutations only — schema additions for `transcribe_md_patients`
-- (weightKg, allergies) at the bottom.

-- 1) New AuditAction enum values for pipeline rejections + AI-output
--    rejections + Rx safety warnings. ADD VALUE IF NOT EXISTS so the
--    migration is idempotent across re-runs.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PIPELINE_REJECTED_TOO_SHORT';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PIPELINE_REJECTED_INSUFFICIENT_TRANSCRIPT';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PIPELINE_FABRICATION_FLAGGED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'CODING_COACH_REJECTED_INVALID_ICD';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'CODING_COACH_REJECTED_INVALID_CPT';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'RX_DOSE_EXCEEDS_VERIFIED_RANGE';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'RX_CONTRAINDICATION_MATCH';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'RX_DRUG_NOT_IN_VERIFIED_DATABASE';

-- 2) TranscribeMdPatient.weightKg — nullable; range-guarded at write time
--    in the API/RSC layer (0.5 .. 200 kg). Required for peds mg/kg dose
--    validation in the Rx safety floor.
ALTER TABLE "transcribe_md_patients"
  ADD COLUMN IF NOT EXISTS "weightKg" DOUBLE PRECISION;

-- 3) TranscribeMdPatient.allergies — String[] with [] default. NULL is
--    impossible (default kicks in); empty array = "no known allergies",
--    populated array = explicit allergens. Postgres TEXT[] default '{}'
--    matches Prisma's `String[] @default([])`.
ALTER TABLE "transcribe_md_patients"
  ADD COLUMN IF NOT EXISTS "allergies" TEXT[] NOT NULL DEFAULT '{}';
