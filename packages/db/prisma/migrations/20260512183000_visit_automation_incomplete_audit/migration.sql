-- Deep-audit G9 closure (2026-05-12).
--
-- Surfaces partial L7 automation failures as auditable events. Pre-fix,
-- if any of L7a (icd-coding) / L7b (cpt-coding) / L7c (rx-drafting)
-- threw mid-pipeline (credit exhaustion, transient API error, validator
-- throw), the visit was silently marked status=READY with NULL columns
-- — the doctor would open the page and see a SOAP with no codes/Rx and
-- no indication that automation failed. The worker change paired with
-- this migration sets needsReview=true + reviewReason on partial
-- failure; THIS enum value gives the audit-row a stable action key so
-- forensics can grep for the pattern across the audit log.
--
-- Idempotent — re-running the migration is a no-op (both halves).

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VISIT_AUTOMATION_INCOMPLETE';

-- ---------------------------------------------------------------------------
-- Historical-victim backfill — visits stuck in the silent-completion
-- state because their original L7 fan-out errored before the worker
-- fix landed. The condition matches the bug-symptom (status=READY +
-- at least one NULL automation column), not specific IDs, so other
-- environments with zero victims get a no-op and prod with N victims
-- gets all N flipped.
--
-- The filter `needsReview = false` makes this idempotent — re-running
-- the migration after the worker-fix landed (when new partial-failures
-- already arrive with needsReview=true) doesn't clobber the existing
-- review-reason text.
--
-- Discovered count on prod at migration write-time: 5 visits, all from
-- 2026-04-19 within a 70-minute window (single-user cluster, single
-- outage). Audit context at docs/qa-reports/specialty-deep-audit-
-- 20260512T182300Z.md §G9.
-- ---------------------------------------------------------------------------

UPDATE transcribe_visits
SET "needsReview" = true,
    "reviewReason" = 'G9 backfill: missing codes detected post-deep-audit (2026-05-12). Click Retry to reprocess.'
WHERE status = 'READY'
  AND ("icdCodes" IS NULL OR "cptCodes" IS NULL OR "rxDrafts" IS NULL)
  AND "deletedAt" IS NULL
  AND "needsReview" = false;
