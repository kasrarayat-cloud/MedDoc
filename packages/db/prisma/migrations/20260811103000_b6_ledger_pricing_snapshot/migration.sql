-- ============================================================================
-- FOUNDATION B6 — THE VERSIONED PRICE SNAPSHOT ON A LEDGER ROW
-- ----------------------------------------------------------------------------
-- SPEC §2.2: a usage row carries "a versioned price-table snapshot — the row
-- records WHICH price table priced it, so a later rate change never re-prices
-- history."
--
-- Ruling 80(e) deferred this deliberately: "`api_usage_events` GAINS NO SNAPSHOT
-- COLUMN IN B3. SPEC §2.2's price-version reference arrives WITH ITS WRITER in
-- B4/B6; a column nothing writes is the half-shipped shape." B6 is the writer,
-- so it arrives now — and it lands on `ledger_entries` rather than on
-- `api_usage_events`, because the priced artifact is the MONEY row.
-- `api_usage_events` records what the vendor counted (B1/B2/B4); this records
-- what we charged for it and on whose authority.
--
-- ⚠️ THIS MIGRATION IS CHEAP TODAY AND IMPOSSIBLE LATER, AND THAT IS WHY IT IS
-- IN B6 RATHER THAN IN B9 WHERE THE RECONCILIATION ACTUALLY READS IT.
-- Ruling 89(e) shipped `bucket` early for exactly this reason: "an APPEND-ONLY
-- TABLE CANNOT BE RETROFITTED — adding it later needs either a DEFAULT (the
-- fail-open shape ruling 67 forbids) or a backfill UPDATE (the one operation
-- this table exists to refuse)." The same argument applies to this column and
-- was not made for it in B5.
--
-- It is free right now for one reason only: `ledger_entries` holds ZERO rows, in
-- production and on QA, so `ADD COLUMN` needs no default and no backfill. That
-- window closes the moment anything writes a row.
--
-- ⚠️ NO CHANGE IS NEEDED TO THE APPEND-ONLY TRIGGER, AND THAT IS BY DESIGN, NOT
-- BY LUCK. `ledger_entries_append_only()` compares
-- `(to_jsonb(NEW) - 'practiceId') = (to_jsonb(OLD) - 'practiceId')` rather than
-- a hand-written column list, precisely so a column added later is covered
-- without anybody remembering to come here. This is the first test of that
-- choice and it passes: the new column is protected from the instant it exists.
-- A column-list guard would have accepted an UPDATE rewriting `pricing` while
-- nulling `practiceId`.
-- ============================================================================

ALTER TABLE "ledger_entries" ADD COLUMN "pricing" JSONB;

COMMENT ON COLUMN "ledger_entries"."pricing" IS
    'B6 / SPEC 2.2 — the versioned price snapshot: which price_rates rows priced this charge, the pre-multiplier cost, and the per-component breakdown. NULL for kinds that are not priced (grant, topup, refund, adjustment); NOT NULL for usage, enforced by ledger_entries_usage_has_pricing.';

-- ============================================================================
-- A `usage` ROW WITHOUT ITS PRICING IS UNREPRESENTABLE
-- ----------------------------------------------------------------------------
-- The column is nullable because most kinds are not priced: a `grant` or a
-- `topup` is money arriving, not money computed, and inventing a pricing object
-- for it would be a claim nobody made. But a `usage` row IS the output of a
-- pricing computation, and one without its snapshot is a charge whose basis has
-- been lost — unreconcilable by B9, and uncorrectable, because the table refuses
-- UPDATE.
--
-- ⚠️ SO THE REQUIREMENT IS CONDITIONAL, AND IT IS IN THE DATABASE RATHER THAN IN
-- THE WRITER. The writer always sets it today; that is a fact about one function
-- and stops being true the first time somebody adds a second writer. The lesson
-- is the AuditAction one, three times over in this repo: the TypeScript layer
-- and the Prisma layer both pass while the database is the only one whose answer
-- counts. So the database holds it.
--
-- A naive "fix" that drops this CHECK to let an unpriced usage row through does
-- not close drift — it removes the guarantee. A usage row that cannot say what
-- priced it is the row B9 will be unable to explain.
-- ============================================================================

ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_usage_has_pricing"
    CHECK ("kind" <> 'usage' OR "pricing" IS NOT NULL);

-- ============================================================================
-- ASSERT WHAT THIS MIGRATION PROMISED — AGENTS.md rule 8.
-- A migration that half-ran and reported success is the failure mode; the only
-- way to tell the difference is to ask afterwards.
--
-- ⚠️ THE ROW-COUNT ASSERTION IS THE LOAD-BEARING ONE. This `ADD COLUMN` is only
-- safe-without-a-default while the table is empty. If it is ever re-run against
-- a populated table — a restored dump, a database that took a writer early —
-- every existing `usage` row would have a NULL `pricing` and the CHECK above
-- would be refused by Postgres anyway. Asserting emptiness FIRST turns that
-- into a clear message instead of a constraint violation nobody can place.
-- ============================================================================
DO $verify$
DECLARE
    n_rows    BIGINT;
    n_col     INT;
    n_check   INT;
BEGIN
    SELECT count(*) INTO n_rows FROM "ledger_entries";
    IF n_rows <> 0 THEN
        RAISE EXCEPTION
            'B6: ledger_entries holds % rows. This migration adds a NOT-NULL-for-usage column with no default and no backfill, which is only correct on an empty table. Do not add a default to make this pass — that is the fail-open shape ruling 67 forbids.',
            n_rows;
    END IF;

    SELECT count(*) INTO n_col
      FROM information_schema.columns
     WHERE table_name = 'ledger_entries' AND column_name = 'pricing';
    IF n_col <> 1 THEN
        RAISE EXCEPTION 'B6: ledger_entries.pricing was not created';
    END IF;

    SELECT count(*) INTO n_check
      FROM pg_constraint
     WHERE conrelid = '"ledger_entries"'::regclass
       AND conname = 'ledger_entries_usage_has_pricing';
    IF n_check <> 1 THEN
        RAISE EXCEPTION 'B6: ledger_entries_usage_has_pricing was not created';
    END IF;

    RAISE NOTICE 'B6: ledger_entries.pricing + ledger_entries_usage_has_pricing verified on an empty table';
END;
$verify$;
