-- Audit actions for the invite gate. AuditAction is a Postgres enum, so these
-- must be added additively — a value cannot be removed without a table rewrite.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'SIGNUP_REJECTED_NO_INVITE';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'WAITLIST_JOINED';
