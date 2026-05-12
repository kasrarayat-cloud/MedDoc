-- Stuck-visit watchdog audit-row coverage (2026-05-12).
--
-- Surfaces the per-minute sweep's force-fail action as an auditable event
-- so an admin can grep audit_logs for VISIT_PROCESSING_TIMEOUT and see
-- which visits the watchdog rescued (or false-positively transitioned).
-- Triggered by the Kasra stuck-visit incident where a 4th-retry within
-- the same minute was silently deduped against the previous failed
-- BullMQ job, pinning the visit at QUEUED for 2.5 hours.
--
-- Idempotent — re-running the migration is a no-op.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VISIT_PROCESSING_TIMEOUT';
