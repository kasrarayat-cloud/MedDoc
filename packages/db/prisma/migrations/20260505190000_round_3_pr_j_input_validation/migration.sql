-- Round 3 PR-J — input validation audit-action expansion.
-- Closes findings A07-P0/P1 (prompt-injection delimiter guard, audio
-- magic-byte sniff, file-size + text-length floors).
--
-- Each ADD VALUE runs in its own implicit subtransaction so a partial
-- apply leaves the enum in a deterministic state. ALTER TYPE ... ADD
-- VALUE IF NOT EXISTS makes the migration idempotent — running twice
-- (e.g., a botched deploy) is a no-op.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PIPELINE_REJECTED_INJECTION_DELIMITER';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'AUDIO_REJECTED_INVALID_MAGIC_BYTES';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'AUDIO_REJECTED_FILE_TOO_LARGE';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEXT_INPUT_REJECTED_TOO_LARGE';
