-- SIGN_BLOCKED_NO_ATTESTATION — the audit row for a sign refused with no attestation.
--
-- ⚠️ THE TS UNION IS NOT THE DATABASE. `audit_logs.action` is a Postgres enum, so
-- adding the label to `lib/audit.ts` made the route emit a value the column could
-- not accept. `logAudit` is fire-and-forget (`void logAudit(...)`), so the insert
-- was rejected and the rejection discarded: on production the sign WAS refused
-- (400 ATTESTATION_REQUIRED, proven on the wire) and the refusal left no trace.
-- A gate that refuses without recording is half a gate.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'SIGN_BLOCKED_NO_ATTESTATION';
