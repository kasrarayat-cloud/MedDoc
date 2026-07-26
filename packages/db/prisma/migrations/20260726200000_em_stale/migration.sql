-- The note changed since the E/M level was last validated.
--
-- DEFAULT false, not true: existing READY visits were scored by the pipeline
-- and nothing has edited them since, so marking every one of them stale would
-- demand a re-confirm on notes that never changed. New mutations set it.
ALTER TABLE "transcribe_visits"
  ADD COLUMN "emStale" BOOLEAN NOT NULL DEFAULT false;
