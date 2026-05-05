-- Coding-coach orphan-completion (EM override persistence).
-- Adds the audit-action enum value emitted when the doctor uses the
-- override dropdown to set a CPT code different from the AI suggestion
-- and the server persists the override into transcribe_visits.cptCodes
-- + writes the audit row. Idempotent (re-running the migration is a
-- no-op).

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EM_OVERRIDE_APPLIED';
