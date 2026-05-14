-- FIND-P1-003 closure (comprehensive-audit 2026-05-14).
--
-- Adds the SPEAKER_ROLE_REASSIGNED audit action so the Layer-2 manual
-- override (doctor reassigning a speaker on the Transcript tab) emits
-- an auditable event. Pre-fix, the action mutated `speakerMap` —
-- which feeds the SOAP note's history-vs-plan segmentation — without
-- a HIPAA §164.312(b) ledger row, leaving "who reassigned what, when"
-- only reconstructable from DB row history.
--
-- Idempotent — re-running the migration is a no-op (IF NOT EXISTS).

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'SPEAKER_ROLE_REASSIGNED';
