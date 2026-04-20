-- T-M17.2 Phase 4: tighten transcribe_visits.patientId to NOT NULL.
-- This is the deferred Commit 3 from the original Phase 1 plan, re-
-- applied after Commits 4-10 (backend + UI) shipped and the running
-- app was confirmed to write patientId on every new-visit path.
--
-- Precondition verified before apply: SELECT COUNT(*) FILTER (WHERE
-- "patientId" IS NULL) FROM transcribe_visits = 0 (18 total rows).
ALTER TABLE "transcribe_visits"
    ALTER COLUMN "patientId" SET NOT NULL;
