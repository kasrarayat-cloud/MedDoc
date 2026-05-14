-- FIND-P1-015 + FIND-P1-016 closure (comprehensive-audit 2026-05-14).
--
-- Adds the MODEL_OUTPUT_VALIDATION_FAIL audit action so the L4 (SOAP
-- generation) and L6 (polish) layers can emit a forensic row when the
-- model returns a body that fails the lenient SOAP-structure check
-- defined at `apps/transcribe-md/src/worker/layers/soap-structure-validator.ts`.
--
-- The failure modes the validator catches — empty output, JSON-shaped
-- output, missing SOAP sections — are recoverable: the layer still
-- persists the raw model output to the column and flips needsReview so
-- the clinician can fix it manually. The audit row gives operators a
-- grep target for "how often is the model regressing the contract".
--
-- Idempotent — re-running the migration is a no-op (IF NOT EXISTS).

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'MODEL_OUTPUT_VALIDATION_FAIL';
