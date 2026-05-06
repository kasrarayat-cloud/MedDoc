-- §164.312(b) audit-row coverage extension — closes 3 P1 gaps surfaced
-- by the QA Interaction Auditor agent v3.2 deep walks
-- (docs/qa-reports/v3.2-discovery-20260506T024044Z.md).
--
--   F-09 — VIEWED_DASHBOARD: emitted when /dashboard reads patient +
--          visit lists (the most-trafficked authenticated landing page,
--          previously unaudited)
--   F-10 — VISIT_CREATED:    emitted when createVisitAction inserts a
--          new transcribe_visits row (visit creation was previously
--          silent at write-time; only VIEWED_VISIT fired later when
--          the doctor navigated into the row)
--   F-11 — VIEWED_SETTINGS:  emitted when /settings reads the user's
--          profile + active sessions (user_sessions.ipAddress and
--          userAgent are device-fingerprint columns, PHI-adjacent
--          under §164.312(b))
--
-- Idempotent (re-running the migration is a no-op).

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VIEWED_DASHBOARD';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VISIT_CREATED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VIEWED_SETTINGS';
