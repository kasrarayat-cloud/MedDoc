-- Distinguish staged MFA enrollment from activation. The existing
-- MFA_ENABLED receipt remains reserved for a verified, enabled factor.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'MFA_ENROLLMENT_STARTED';

COMMIT;
