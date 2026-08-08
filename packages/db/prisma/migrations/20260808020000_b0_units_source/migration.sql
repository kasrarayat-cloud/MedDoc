-- ===========================================================================
-- B0 — `api_usage_events.unitsSource`: where a row's UNITS came from.
-- ---------------------------------------------------------------------------
-- STEP 1 OF TWO. This migration adds the column NULLABLE and backfills every
-- existing row to 'vendor'. A LATER migration sets NOT NULL, after the code
-- that writes the column is live everywhere.
--
-- ⚠️ WHY IT IS SPLIT, AND WHY DOING IT IN ONE STEP WOULD BREAK THE METER.
-- `scripts/deploy-prod.sh` applies migrations at step 3 and only recreates
-- transcribe-md / transcribe-md-worker at step 6. Between those two steps the
-- PREVIOUS image is still serving and still writing usage rows — and it has
-- never heard of this column. A NOT NULL column with no default would make
-- every one of those inserts fail, during the very deploy that is supposed to
-- make the meter trustworthy. The failure would be quiet, too: logApiUsage is
-- fire-and-forget and swallows its own errors to console.warn.
--
-- ⚠️ AND IT WILL NEVER TAKE A DEFAULT — not now, not in step 2.
-- A provenance column whose default is the TRUSTED value is fail-open: any
-- future writer that has not heard of it silently produces a row asserting that
-- a real vendor reported these numbers. `DEFAULT 'vendor'` would be exactly the
-- fail-open `?? 'clinic_main'` that T2 spent a security block removing from
-- audit attribution. The obligation lives in the TypeScript type instead
-- (`UsageEvent.unitsSource` is required), so a new writer fails to COMPILE.
--
-- THE BACKFILL IS FACTUALLY CORRECT, NOT A CONVENIENCE. Every existing row was
-- written by a code path that only runs when a real vendor call was made — the
-- mock short-circuits sat ABOVE the meter, which is the bug B0 fixes. So no
-- historical row can be a mock row. Verified: production holds 0 rows written
-- under MOCK_AI_CALLS, because under mock nothing reached logApiUsage at all.
-- ===========================================================================

ALTER TABLE "api_usage_events" ADD COLUMN "unitsSource" TEXT;

UPDATE "api_usage_events" SET "unitsSource" = 'vendor' WHERE "unitsSource" IS NULL;

-- Guard: the backfill must leave nothing behind. If a row survives this, the
-- assumption above ("every existing row is a vendor row") was wrong and the
-- step-2 NOT NULL would abort later, further from the cause.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM api_usage_events WHERE "unitsSource" IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION '[b0] % api_usage_events rows still have a NULL unitsSource after the backfill.', n;
  END IF;
  RAISE NOTICE '[b0] unitsSource added nullable and backfilled to vendor';
END $$;

CREATE INDEX "api_usage_events_unitsSource_timestamp_idx"
  ON "api_usage_events" ("unitsSource", "timestamp");
