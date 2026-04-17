-- Chart IDs are practice-scoped. Composite unique on (practiceId, chartId)
-- so Practice A's C-1001 is independent of Practice B's C-1001. Postgres
-- treats multiple NULLs as distinct, so patients without a chartId are
-- unaffected. Serves as the race-condition gate for auto-generated IDs:
-- the data layer generates max(chartId)+1 then retries on collision.
ALTER TABLE "patients"
  ADD CONSTRAINT "patient_practice_chartid_unique"
  UNIQUE ("practiceId", "chartId");
