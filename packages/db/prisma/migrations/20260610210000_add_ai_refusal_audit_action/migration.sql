-- Q1 #09.1 — Anthropic content-policy refusal categorization.
-- ----------------------------------------------------------------------------
-- Add the `AI_REFUSAL` enum value to AuditAction. The worker's outer catch
-- emits a row with this action when a layer's Anthropic call returns
-- `stop_reason: 'refusal'`. The refusal is categorized PERMANENT (no retry
-- burn) and the visit fails fast into the BullMQ DLQ. Metadata carries
-- { layer, model, purpose? } — never model output.
--
-- Idempotent: `ADD VALUE IF NOT EXISTS` (Postgres 9.6+). Adding an enum value
-- is non-blocking and cannot break in-flight rows.
-- ============================================================================

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'AI_REFUSAL';
