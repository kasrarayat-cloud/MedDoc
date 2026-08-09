-- ===========================================================================
-- B1-b STEP 2 — `api_usage_events.requestId` stops being a column that is
-- always populated and starts being a column that is always TRUE.
-- ---------------------------------------------------------------------------
-- Ruled 2026-08-09 (RULINGS.md, "B1-b — requestId goes NULLABLE with a
-- provenance-tied CHECK, in TWO STEPS"). This is step (a): decidable without
-- data, and deliberately the SAFE half.
--
-- What was wrong with the column, in its own schema's words. `schema.prisma`
-- has said this about `ai_calls.requestId` since B1-a:
--
--     Unambiguous BY CONSTRUCTION on this table specifically: `ai_calls` is a
--     REAL-VENDOR-CALLS-ONLY table, so a non-null value here is always a real
--     vendor's id. `api_usage_events.requestId` does NOT have that property —
--     it is NOT NULL, it carries mock rows, and it still falls back to
--     `randomUUID()`. Closing that is B1-b and it needs a ruling.
--
-- Three defects, named there, and this migration plus its commit closes all
-- three. The database half is here; the writer half is in `api-usage.ts`.
--
-- ── THE DIRECTION OF THE CHECK IS THE RULING, NOT A DETAIL ────────────────
--
--     requestId IS NOT NULL  ⇒  unitsSource = 'vendor'
--
-- Read it as the sentence it is: AN ID PRESENT MEANS A REAL VENDOR GAVE US
-- ONE. Only vendor rows may ever carry an id; a mock row carries NULL, never a
-- minted value. A fabricated id wearing the vendor's shape is exactly the
-- provenance-confusion class the `unitsSource` ruling exists to prevent, and it
-- is worse here than a NULL would be: one row later nothing distinguishes it
-- from a real correlation id, so it does not merely lose information, it
-- manufactures false information.
--
-- ⚠️ THE CONVERSE IS DELIBERATELY *NOT* ASSERTED, AND THAT IS STEP (b).
-- Whether `vendor ⇒ id` can be strict — the full biconditional — depends on how
-- often a real vendor call genuinely yields no id, which is a MEASUREMENT this
-- programme has not taken yet (it is step 4's smoke). Asserting it now would be
-- guessing dressed as engineering, and guessing in the direction that CANNOT be
-- walked back: tightening later is always available, because a gate only ever
-- gains requirements. Loosening a shipped constraint is the move this ordering
-- exists to avoid having to make.
--
-- ── A NO-OP ON CURRENT DATA, AND THE GUARD IS WHAT PROVES IT ──────────────
-- Measured on production immediately before writing this:
--
--     1312 rows · 0 with a NULL requestId · 1312 'vendor' · 0 'mock'
--
-- Every existing row is (id present, vendor), which satisfies the implication
-- unchanged. `DROP NOT NULL` widens what is legal and cannot reject a row that
-- is already there. So on today's data this migration is expected to move
-- nothing, and the abort guard below is the difference between knowing that and
-- assuming it.
--
-- ── THE WRITE-PATH SWEEP, BY TABLE ────────────────────────────────────────
-- The universe was swept by TABLE, per the standing rule, and not by whatever
-- the type checker surfaced:
--
--     raw SQL   grep -rniE 'insert into "?api_usage_events'   → 1 site
--                 apps/transcribe-md/tests/e2e/scenarios/38-usage-provenance.spec.ts:65
--     ORM       apiUsageEvent.(create|upsert|createMany)      → 1 site
--                 packages/ai/src/api-usage.ts:143
--
-- The raw-SQL count was POSITIVE-CONTROLLED: the same pattern against
-- `transcribe_visits` returns 7, so the number is a measurement and not a
-- broken pattern. Both sites are handled in this commit, and the E2E one is not
-- incidental — its fixture inserts a MOCK row carrying 'b0gate-req', which this
-- CHECK refuses. Two of that spec's arms would have gone red, correctly, and
-- they are updated to encode the new rule rather than to route around it.
--
-- ⚠️ AND `tsc` CANNOT SEE THE ORM WRITER — it is `(prisma as any)
-- .apiUsageEvent.create(...)`. A clean type-check proves nothing about this
-- insert; it was read by hand, as B0-b's header also records.
--
-- ⚠️ THE SILENT FAILURE THIS ORDERING AVOIDS. `logApiUsage` is fire-and-forget:
-- it catches its own write error and console.warns. Had the CHECK landed while
-- the builders still minted `randomUUID()`, every MOCK row would have been
-- refused by the database and DROPPED with no test failing and no surface going
-- red — silently undoing B0-a, whose entire point was that a mocked run meters.
-- The writer change ships in the SAME commit for that reason, and the gate
-- reads the row back rather than trusting the status of the call.
-- ===========================================================================

-- 1. ABORT if any existing row would violate the implication.
--
-- Ordered BEFORE the constraint on purpose. `ADD CONSTRAINT` would reject the
-- migration anyway, but it would do so naming the constraint and not the cause,
-- and a migration that half-ran and reported success is the failure mode the
-- standing rule is written against. This says which rows and how many.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
    FROM api_usage_events
   WHERE "requestId" IS NOT NULL AND "unitsSource" <> 'vendor';
  IF n > 0 THEN
    RAISE EXCEPTION '[b1b-step2] % api_usage_events rows carry a requestId on a non-vendor provenance; refusing to add the CHECK. These are fabricated ids on mock rows — clear them before re-running.', n;
  END IF;
END $$;

-- 2. The column stops lying by omission. NULL now means what it should always
--    have meant: the vendor did not tell us. It is not an absence of data, it
--    is a recorded fact about the vendor's response.
ALTER TABLE "api_usage_events" ALTER COLUMN "requestId" DROP NOT NULL;

-- 3. The guarantee itself.
ALTER TABLE "api_usage_events"
  ADD CONSTRAINT "api_usage_events_request_id_requires_vendor"
  CHECK ("requestId" IS NULL OR "unitsSource" = 'vendor');

-- 4. Assert the shape we just claimed, rather than trusting step 2's exit code.
--    `DROP NOT NULL` on an already-nullable column succeeds silently, and so
--    does one on a column that some earlier migration already changed; neither
--    is distinguishable from success without reading the catalog back.
DO $$
DECLARE nullable text; has_check int;
BEGIN
  SELECT is_nullable INTO nullable
    FROM information_schema.columns
   WHERE table_name = 'api_usage_events' AND column_name = 'requestId';
  IF nullable <> 'YES' THEN
    RAISE EXCEPTION '[b1b-step2] requestId is still NOT NULL after DROP NOT NULL (is_nullable=%).', nullable;
  END IF;

  SELECT count(*) INTO has_check
    FROM pg_constraint
   WHERE conname = 'api_usage_events_request_id_requires_vendor';
  IF has_check <> 1 THEN
    RAISE EXCEPTION '[b1b-step2] the request-id CHECK is absent after ADD CONSTRAINT (found %).', has_check;
  END IF;

  RAISE NOTICE '[b1b-step2] requestId is NULLABLE and an id now implies unitsSource=vendor';
END $$;
