-- Phase 17 — close the §164.312(b) audit-completeness gaps from the
-- Phase 16 deep audit. Each new value tags a PHI-touching mutation
-- that previously executed without an audit row.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'AUDIO_UPLOADED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'DOC_EDITOR_SAVED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'DOC_EDITOR_AI_SUGGESTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PHI_EXTRACTED_FROM_VOICE';
