-- BATCHED AUDIT-ENUM LABELS — four values, one irreversible act.
--
-- ⚠️ POSTGRES HAS NO `ALTER TYPE … DROP VALUE`. Every line below is permanent.
-- Three separate needs had each accrued a pending migration; batching them means
-- ONE irreversible act to declare and judge under §2.5 rather than three.
--
-- ⚠️ `IF NOT EXISTS` IS DELIBERATE, NOT DEFENSIVE PADDING. It makes the migration
-- idempotent so a partial application cannot wedge the deploy half-way through a
-- four-statement change — the half-landed shape this repo has been bitten by.
--
--   EM_OMITTED_IN_SIGNED_ARTIFACT  ruling #155(b) — visibility without mutation
--   TEMPLATE_DELETED               R1 — the SUCCESSFUL delete, previously traceless
--   TEMPLATE_ARCHIVED              R1 — the non-destructive alternative
--   ICD_CODE_AUTO_ACCEPTED         F8-S3 — reserved; the threshold is NOT settled
--   TEMPLATE_PROVENANCE_LOST       the 29 retrospective annotations — NOT a deletion
--
-- ⚠️ THE FIFTH LABEL EXISTS BECAUSE A PROVENANCE LOSS IS NOT A DELETION EVENT.
-- Annotating the 29 with TEMPLATE_DELETED would have made an append-only trail
-- assert that 29 deletions happened today. It has NO RUNTIME WRITER by design:
-- ruled mutation acts write it, the annotation backfill being the first.
--
-- 148 -> 153.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EM_OMITTED_IN_SIGNED_ARTIFACT';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_DELETED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_ARCHIVED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'ICD_CODE_AUTO_ACCEPTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_PROVENANCE_LOST';
