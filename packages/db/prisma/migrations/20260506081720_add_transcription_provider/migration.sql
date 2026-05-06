-- PR-L follow-up — wire transcribe() orchestrator into Layer-1.
-- ----------------------------------------------------------------------------
-- Two changes in one migration:
--   1. Add `transcriptionProvider` text column to transcribe_visits.
--      Records which provider produced the transcript on the most-
--      recent (re-)processing pass. NULL on legacy rows; the worker
--      sets it on every new transcription.
--   2. Add `TRANSCRIPTION_PROVIDER_FALLBACK` enum value to AuditAction.
--      Layer-1 emits a row with this action whenever Deepgram primary
--      fails and Whisper saves the visit — the canary signal ops
--      reads in /admin/queues + audit_logs.
--
-- Idempotent (re-running the migration is a no-op):
--   - `ADD COLUMN IF NOT EXISTS` on the column add.
--   - `ADD VALUE IF NOT EXISTS` on the enum (Postgres 9.6+ supports it).
-- ============================================================================

ALTER TABLE "transcribe_visits"
  ADD COLUMN IF NOT EXISTS "transcriptionProvider" TEXT;

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TRANSCRIPTION_PROVIDER_FALLBACK';
