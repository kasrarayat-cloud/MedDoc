-- Phase 19 — close h16-audit-gap-realtime. WebRTC voice session
-- lifecycle on /api/realtime/* now writes audit rows.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'REALTIME_SESSION_STARTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'REALTIME_SESSION_ENDED';
