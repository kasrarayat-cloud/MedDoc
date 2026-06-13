-- E/M recompute on adoption: visible-confirm, never silent (2026-06-12,
-- prod smoke #311 follow-up — adopting a med-change suggestion recomputed
-- the suggested E/M code 99213 → 99214 silently).
-- 1) emPendingChange JSONB — set by the adopt/dismiss suggestion actions
--    when the action changed the computed E/M level. Shape: { from, to,
--    cause, at, acknowledgedAt? } — CPT codes + cause class + ISO
--    timestamps only, never note text. An entry WITHOUT acknowledgedAt
--    blocks POST /api/visits/[id]/sign until the doctor explicitly
--    confirms the new level; the winning READY→SIGNED transition stamps
--    acknowledgedAt. NULL when no suggestion action has changed the level.
-- 2) Audit actions: EM_LEVEL_CHANGED (metadata EXACTLY {from, to, cause},
--    cause ∈ 'suggestion_adopted'|'suggestion_dismissed') on the suggestion
--    action that changed the level; EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE
--    when a sign request was rejected for lacking the acknowledgement.
-- Additive only; safe on a live database.
ALTER TABLE "transcribe_visits" ADD COLUMN IF NOT EXISTS "emPendingChange" JSONB;
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EM_LEVEL_CHANGED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE';
