-- T-M17.3 Phase 1: soft-delete + archive columns on transcribe_visits.
--
-- Both are nullable timestamps; NULL = visible in default queries.
-- SIGNED visits use `archivedAt` (HIPAA retention forbids delete);
-- all other statuses use `deletedAt` (15-day trash before the cron
-- hard-deletes).
--
-- Compound index on (patientId, deletedAt, archivedAt) supports the
-- dominant query shape across every surface — patient timeline,
-- dashboard visits tab, per-patient aggregates — which pairs
-- patientId with an "IS NULL AND IS NULL" filter.
ALTER TABLE "transcribe_visits" ADD COLUMN "deletedAt"  TIMESTAMPTZ(6);
ALTER TABLE "transcribe_visits" ADD COLUMN "archivedAt" TIMESTAMPTZ(6);

CREATE INDEX "transcribe_visits_patientId_deletedAt_archivedAt_idx"
    ON "transcribe_visits"("patientId", "deletedAt", "archivedAt");
