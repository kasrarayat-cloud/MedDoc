-- Coding-coach stub-completion (EM bump-additions persistence).
-- Adds the audit-action enum value emitted when the doctor accepts a
-- bump suggestion and the server merges the additions into the SOAP
-- draft + re-runs the L7b CPT scorer. Idempotent (re-running the
-- migration is a no-op).

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EM_BUMP_APPLIED';
