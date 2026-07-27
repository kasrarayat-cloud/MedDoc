-- Sign refused because the note changed since the E/M level was last scored.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EM_SIGN_BLOCKED_STALE';
