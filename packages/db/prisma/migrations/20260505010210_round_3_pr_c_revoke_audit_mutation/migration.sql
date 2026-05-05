-- Round 3 PR-C — HIPAA §164.312(c) integrity safeguard.
-- Audit finding A09-P0-002: `audit_logs` is application-mutable.
-- The `meddoc` Postgres role (used by every app container) had full
-- DML rights on the audit table — meaning the same code path that
-- reads PHI could also delete the audit trail of having read it.
--
-- This migration revokes UPDATE / DELETE / TRUNCATE on `audit_logs`
-- from the `meddoc` role. INSERT (logAudit) and SELECT (admin
-- dashboard) are explicitly granted so the app continues to function.
--
-- Schema-level TRUNCATE revoke is defense-in-depth: even if a future
-- migration accidentally re-grants DELETE on a specific table, the
-- meddoc role cannot wholesale-truncate the schema.
--
-- A smoke test asserting this revoke held lives at:
--   apps/transcribe-md/tests/integrity/audit-logs-immutable.test.ts
--
-- Rollback (only via superuser, e.g. `postgres`):
--   GRANT UPDATE, DELETE, TRUNCATE ON TABLE audit_logs TO meddoc;
-- (do not commit a rollback path; if this needs reverting, that's an
--  incident-response decision, not a routine schema migration.)

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM meddoc;
GRANT INSERT, SELECT ON TABLE audit_logs TO meddoc;

-- Defense-in-depth: the meddoc role should never need TRUNCATE on
-- ANY table in production. Test code uses a separate test role.
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM meddoc;
