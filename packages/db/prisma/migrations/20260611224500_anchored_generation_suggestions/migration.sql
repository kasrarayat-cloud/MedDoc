-- Hybrid anchored generation (2026-06-11, flag-gated; design:
-- docs/strategy/evidence-anchored-generation-20260611T214934Z.md).
-- 1) suggestedClaims JSONB — claims the fail-closed verifier demoted from
--    the note body, rendered in the "Suggested by AI" lane. NULL when the
--    flag is off (prod default) — fully backward compatible.
-- 2) Audit actions for the explicit doctor adoption flow (PHI-safe
--    metadata: counts/section/reason class only, never claim text).
-- Additive only; safe on a live database.
ALTER TABLE "transcribe_visits" ADD COLUMN IF NOT EXISTS "suggestedClaims" JSONB;
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'SUGGESTION_ADOPTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'SUGGESTION_DISMISSED';
