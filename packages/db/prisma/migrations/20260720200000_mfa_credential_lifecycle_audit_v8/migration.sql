-- Preserve distinct immutable receipts for physician recovery-code rotation
-- and the one-time encrypted MFA credential migration. Neither event is an
-- MFA enable/disable transition.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'MFA_RECOVERY_CODES_ROTATED';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'MFA_CREDENTIALS_MIGRATED';

COMMIT;
