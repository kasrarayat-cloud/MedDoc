-- ===========================================================================
-- B0 — `api_usage_events.unitsSource`: STEP 2 OF TWO. The database's guarantee
-- catches up with the type's.
-- ---------------------------------------------------------------------------
-- Step 1 (`20260808020000_b0_units_source`) added the column NULLABLE and
-- backfilled every row to 'vendor'. It said, in as many words, that a LATER
-- migration would set NOT NULL "after the code that writes the column is live
-- everywhere". That condition is now met: B0-a deployed to production on
-- 2026-08-08T18:40Z (`main` @ 87327db6), so every image that can reach this
-- table sets the column explicitly.
--
-- Until this lands the database is weaker than the TypeScript type: a writer
-- that reaches `api_usage_events` off the typed path can still insert a NULL
-- provenance, and a NULL provenance is a row that claims nothing about whether
-- a vendor was called.
--
-- ⚠️ STILL NO DEFAULT, AND THAT IS THE POINT OF THE WHOLE COLUMN.
-- Ruled 2026-08-08 (RULINGS.md, "A provenance column's DEFAULT must never be
-- the TRUSTED value"). `DEFAULT 'vendor'` would let any future writer that has
-- never heard of this column silently assert that a real vendor reported these
-- numbers — the fail-open shape of T2's `?? 'clinic_main'`. The obligation
-- lives in the type (`UsageEvent.unitsSource` is required), so a new writer
-- fails to COMPILE; and from here it also fails to INSERT.
--
-- ── THE WRITE-PATH SWEEP, BY TABLE ────────────────────────────────────────
-- Per the standing rule, the universe was swept by TABLE and not by whatever
-- the type checker happened to surface:
--
--     raw SQL   grep -rniE 'insert into "?api_usage_events'   → 0 sites
--     ORM       apiUsageEvent.(create|upsert|createMany)      → 1 site
--                 packages/ai/src/api-usage.ts:143
--
-- The raw-SQL zero was POSITIVE-CONTROLLED: the same pattern against
-- `transcribe_visits` returns 7 real inserts, so the zero is an empty set and
-- not a broken pattern. Every other `api_usage_events` reference in the tree is
-- a SELECT (the /admin/usage rollups).
--
-- ⚠️ AND `tsc` CANNOT SEE THE ONE WRITER. It is `(prisma as any).apiUsageEvent
-- .create(...)` — the shared client is untyped there, so a type-check clean bill
-- proves nothing about this insert. It was read by hand. The type obligation is
-- enforced one layer up, at `logApiUsage(event: UsageEvent)`, which is where
-- B0-a's eight call sites were enumerated from.
--
-- ── THE STRAGGLER BACKFILL IS FACTUALLY CORRECT, NOT A CONVENIENCE ────────
-- Any row that is still NULL was written by a PRE-B0-a image — the only code
-- that ever omitted this column. In that code the mock short-circuits sat ABOVE
-- the meter, so nothing under MOCK_AI_CALLS ever reached `logApiUsage` at all.
-- A pre-B0-a usage row is therefore a real vendor call by construction, and
-- 'vendor' is the true value rather than a convenient one.
--
-- Measured on production immediately before writing this: 1312 rows, all
-- 'vendor', 0 NULL — so on prod the UPDATE below is expected to touch nothing
-- and the guard is what proves it.
--
-- ⚠️ THE DOMAIN CHECK IS AN ADDITION BEYOND THE LITERAL TWO-STEP RULING, AND
-- IT IS FLAGGED AS ONE. The ruling named "nullable + backfill, then NOT NULL".
-- NOT NULL alone still permits any TEXT. That matters because the rollups
-- filter `WHERE "unitsSource" = 'vendor'` and B6 will compute money over
-- exactly those rows: a row carrying 'Vendor' or 'real' lands in NEITHER the
-- vendor bucket nor the mock bucket. It would not be an error anywhere — it
-- would simply stop being counted, which is an UNDERCHARGE that no test can
-- see; and the mirror case (a mock row miscounted as vendor) charges a doctor
-- for a call that never happened. The ruling already fixed the domain as
-- `vendor | mock`; this makes the database the layer that enforces it, per the
-- AuditAction lesson that the database is the only layer whose answer counts.
--
-- COST, STATED: adding a third provenance value later needs a migration to
-- widen this CHECK. That is deliberate, and it is the same deliberateness the
-- three-layer AuditAction failure argued for.
-- ===========================================================================

-- 1. Sweep up any straggler written by a pre-B0-a image.
UPDATE "api_usage_events" SET "unitsSource" = 'vendor' WHERE "unitsSource" IS NULL;

-- 2. ABORT before SET NOT NULL if anything is still underivable.
--
-- With a blanket backfill directly above, this can only fire if that UPDATE did
-- not apply — which is exactly what it is for. It is the occurrence assertion a
-- scripted edit owes: a statement that silently affects zero rows and a
-- statement that worked are indistinguishable without it. A partially
-- backfilled column that then takes NOT NULL is a migration that half-ran and
-- reported success.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM api_usage_events WHERE "unitsSource" IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION '[b0-step2] % api_usage_events rows still have a NULL unitsSource; refusing to SET NOT NULL.', n;
  END IF;
END $$;

-- 3. Values outside the ruled domain would survive NOT NULL. Name them now,
--    before the money code reads this column.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM api_usage_events WHERE "unitsSource" NOT IN ('vendor', 'mock');
  IF n > 0 THEN
    RAISE EXCEPTION '[b0-step2] % api_usage_events rows carry a unitsSource outside (vendor, mock).', n;
  END IF;
END $$;

-- 4. The guarantees themselves.
ALTER TABLE "api_usage_events" ALTER COLUMN "unitsSource" SET NOT NULL;

ALTER TABLE "api_usage_events"
  ADD CONSTRAINT "api_usage_events_units_source_domain"
  CHECK ("unitsSource" IN ('vendor', 'mock'));

DO $$
BEGIN
  RAISE NOTICE '[b0-step2] unitsSource is NOT NULL and domain-constrained to (vendor, mock)';
END $$;
