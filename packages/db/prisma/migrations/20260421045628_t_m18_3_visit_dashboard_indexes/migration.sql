-- T-M18.3 A23 + A24: add two indexes on transcribe_visits.
--
-- A23 — (userId, deletedAt, archivedAt) mirrors the T-M17.3 per-patient
-- composite but for the per-user selector used on /dashboard, where
-- patientId isn't narrowed. At pilot scale the existing (userId,
-- createdAt) index still serves the sort; A23 removes the post-filter
-- on the two IS-NULL predicates at volume (~1000+ visits/user).
--
-- A24 — (deletedAt) supports the 15-day stale-trash sweep's
-- `deletedAt < cutoff` scan. Plain btree because Prisma's schema DSL
-- doesn't expose partial indexes yet; the cost of indexing NULLs is
-- negligible at current scale and a seq-scan replacement when the
-- trash row count grows.
CREATE INDEX "transcribe_visits_userId_deletedAt_archivedAt_idx"
    ON "transcribe_visits"("userId", "deletedAt", "archivedAt");

CREATE INDEX "transcribe_visits_deletedAt_idx"
    ON "transcribe_visits"("deletedAt");
