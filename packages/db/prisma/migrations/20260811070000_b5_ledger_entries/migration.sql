-- ============================================================================
-- FOUNDATION B5 — MONEY. THE APPEND-ONLY LEDGER AND THE PRACTICE WALLET.
-- ----------------------------------------------------------------------------
-- SPEC §2.1 (integer micro-unit money; append-only LedgerEntry with
-- balanceAfter; the wallet is a property of the PRACTICE, not the user),
-- §4.4 / GATE 0.4 (integer micro-dollars ledger-wide, no float anywhere).
--
-- WHAT THIS MIGRATION CLAIMS, AND WHAT IT DOES NOT
--
--   It claims: a practice's balance is a running sum that the DATABASE derives
--   and the database refuses to let anybody edit or erase. Not by convention,
--   not by a code review habit — an UPDATE and a DELETE are both rejected by
--   the storage layer, the way T3's composite FK rejects a cross-tenant visit.
--
--   It does NOT claim that anything is billed, charged, granted or debited.
--   NOTHING WRITES THIS TABLE. There is no application writer, no wallet read
--   path, no balance check — those are B6 (`charge = cost × 3 / 2`, the
--   prod-only writer), B7 (Stripe top-ups) and B8 (the fail-closed block). This
--   ships the same way B3's price table shipped: the shape and its guarantees
--   first, with nothing reading it, so the writer is built against a table that
--   already refuses to be wrong. A column nothing writes is the half-shipped
--   shape (ruling 80(e)) — an empty table whose CONSTRAINTS are the deliverable
--   is not.
--
--   It does NOT decide the promo bucket's SIZE or who grants it. SPEC §2.4's
--   "$10 promo bucket" is B7's. What is decided here is only that `paid` and
--   `promo` are two SEPARATE running balances rather than one number with a
--   note — because that is the decision an append-only table cannot be
--   retrofitted with. See "WHY THE BUCKET EXISTS NOW" below.
--
-- ── THE FIVE GUARANTEES ────────────────────────────────────────────────────
--
--   1. APPEND-ONLY, AT THE DATABASE.  UPDATE, DELETE and TRUNCATE are all
--      refused by triggers. A correction is another row (SPEC §2.1).
--   2. THE BALANCE IS DERIVED, NEVER THREADED.  `balanceAfter` and `seq` are
--      computed by the INSERT trigger from the previous row. A caller-supplied
--      value is IGNORED, not trusted and not validated.
--   3. THE SEQUENCE IS GAPLESS AND UNIQUE per (practice, bucket).
--   4. NO FLOAT EVER TOUCHES MONEY.  BIGINT micro-dollars, GATE 0.4.
--   5. THE ROW OUTLIVES THE PRACTICE.  Deleting an account detaches the
--      ledger; it never deletes it.
--
-- ============================================================================
-- WHY THE BALANCE IS DERIVED BY THE DATABASE AND NOT PASSED IN
-- ----------------------------------------------------------------------------
-- AGENTS.md: "Prefer DERIVING the value in the query over threading a
-- parameter. A hand-passed value can only be correct or rejected; a derived one
-- cannot drift." T3's raw-SQL sites take `(select "practiceId" from … )` for
-- exactly this reason.
--
-- A ledger is the worst possible place for a threaded value, because the table
-- is APPEND-ONLY: a wrong `balanceAfter` can never be corrected in place. It
-- would have to be superseded by an `adjustment` row that is itself computed
-- from the wrong number. So the caller does not get to have an opinion —
-- `ledger_entries_derive()` overwrites whatever arrived.
--
-- ⚠️ NOTE WHAT THIS RULES OUT AND WHAT IT DOES NOT. It rules out drift between
-- what the caller thinks the balance is and what the ledger says. It does NOT
-- rule out the caller inserting the wrong AMOUNT — no database can check that.
-- The amount is the caller's claim; the balance is the database's arithmetic.
--
-- ============================================================================
-- WHY THE BUCKET EXISTS NOW, IN B5, RATHER THAN IN B7 WHERE THE PROMO LIVES
-- ----------------------------------------------------------------------------
-- Because an APPEND-ONLY TABLE CANNOT BE RETROFITTED. Adding a `bucket` column
-- to a populated ledger later means either (a) a DEFAULT, which is the
-- fail-open provenance shape ruling 67 forbids — every historical row would
-- silently assert a bucket nobody chose — or (b) an UPDATE to backfill it,
-- which is the one operation this table exists to refuse.
--
-- The cost of deciding it now is one CHECK constraint. The cost of deciding it
-- later is a migration that has to defeat the table's central guarantee to run.
--
-- ============================================================================
-- WHY THERE IS NO `balanceAfter >= 0` CHECK — AND THIS IS DELIBERATE
-- ----------------------------------------------------------------------------
-- It would look like the obvious safety rail and it would break clinical work.
--
-- SPEC §2.4's insufficient-balance block is checked BEFORE the pipeline runs;
-- the `usage` rows land AFTER, when the vendors report what they actually
-- charged. A visit admitted with a sufficient balance can legitimately overrun
-- it — the meter cannot know a call's cost until the call returns. A CHECK here
-- would make the LAST usage row of such a visit unrepresentable, and the row
-- that fails to land is the one recording money we already owe a vendor.
--
-- Fail-closed belongs at ADMISSION (B8), where refusing costs nothing. It does
-- not belong at RECORDING, where refusing loses the record of a real debt.
--
-- ============================================================================
-- WHY THE SIGN RULES STOP AT THREE KINDS
-- ----------------------------------------------------------------------------
-- `usage <= 0`, `topup > 0`, `grant > 0` are asserted. `refund` and
-- `adjustment` are NOT sign-constrained, and the omission is the considered
-- part.
--
-- "Refund" has two defensible readings in a wallet system — the practice's
-- balance is CREDITED (we refund them into the wallet), or the practice's card
-- is refunded and the wallet is DEBITED. Nothing in SPEC settles it, and B8's
-- system-fault auto-credit could reasonably be filed under either `refund` or
-- `adjustment`. Guessing would be the FORBIDDEN direction: if the guess is
-- wrong the fix is to WEAKEN a constraint that already shipped. Leaving it open
-- means the fix is to ADD one, which is the allowed direction.
--
-- `usage <= 0` and not `< 0`: a call whose cost rounds to zero micro-dollars is
-- representable, and a zero-cost usage row is a true statement about a call
-- that happened. `> 0` on topup and grant is strict because a zero top-up is a
-- row asserting that nothing happened.
--
-- ============================================================================
-- WHY A TRIGGER AND NOT `REVOKE UPDATE, DELETE`
-- ----------------------------------------------------------------------------
-- Because this database has ONE login role and it is SUPERUSER. That is
-- recorded, measured, in RELAY's SECURITY BLOCK row: "Postgres has ONE login
-- role, SUPERUSER" — credentials are shared, not separable, across three
-- containers.
--
-- A superuser bypasses table privileges entirely, so a `REVOKE` here would be a
-- decoration: it would appear in `\dp`, satisfy a reviewer, and stop nothing. A
-- superuser does NOT bypass triggers. The trigger is the only mechanism that
-- actually enforces on the system as it is, rather than on the system as a
-- least-privilege design would have it.
--
-- (If per-role credentials ever land — RELAY routes that to TEAMS hygiene — a
-- REVOKE becomes a worthwhile SECOND layer. It is not a replacement for this
-- one, and it must not be read as making this trigger redundant.)
--
-- ============================================================================
-- WHY THE PRACTICE DETACHES INSTEAD OF RESTRICTING — AND WHY THE APPEND-ONLY
-- TRIGGER HAS EXACTLY ONE HOLE IN IT
-- ----------------------------------------------------------------------------
-- This was not decided here. It was decided already, and the decision is
-- written in the code that deletes accounts —
-- `apps/transcribe-md/src/app/api/settings/delete-account/route.ts:184`:
--
--     "audit_logs and billing_events are deliberately absent from this list:
--      they DETACH (SET NULL) when the practice goes, because an audit trail
--      and A FINANCIAL RECORD must outlive the account they describe."
--
-- A billing ledger is a financial record by definition, so it takes the shape
-- the house already ruled for financial records: `practiceId` NULLABLE with
-- `ON DELETE SET NULL`, plus a `practiceIdSnapshot` tombstone carrying no FK —
-- the exact pair `audit_logs` uses (`schema.prisma:1202-1211`, the S4c rule).
--
-- ⚠️ RESTRICT WAS THE OTHER CANDIDATE AND IT IS THE ONE THAT LOOKS SAFER. It is
-- not. `audit_logs` HAD a RESTRICT there and it "made account deletion
-- impossible instead" — S4c exists because of that. And the same shape has
-- already bitten this repo twice more: `RxWarningOverride`'s RESTRICT FK
-- "silently blocked the whole cascade for any doctor who had ever overridden an
-- Rx warning" (same file, line 176). A RESTRICT on an append-only table is
-- strictly worse than on a normal one, because there is no delete that could
-- ever clear the blocker.
--
-- ⚠️ SO `ON DELETE SET NULL` MUST BE PERMITTED THROUGH AN APPEND-ONLY TRIGGER,
-- BECAUSE POSTGRES IMPLEMENTS IT AS AN UPDATE. A blanket "no UPDATE" would
-- refuse the detach, and the practice delete would fail — exactly the S4c
-- failure, arriving from the other side. The hole is therefore cut to the exact
-- shape of that one operation:
--
--     an UPDATE is permitted IFF `practiceId` goes NOT NULL → NULL
--     AND EVERY OTHER COLUMN IS BYTE-IDENTICAL.
--
-- ⚠️ AND "EVERY OTHER COLUMN" IS COMPARED AS `to_jsonb(NEW) - 'practiceId'`,
-- NOT AS A HAND-WRITTEN COLUMN LIST. AGENTS.md: "a per-caller list is kept
-- complete by hand, and hand-kept lists are wrong eventually. Put the behaviour
-- where it cannot be forgotten." A column added to this table in five years is
-- covered by the jsonb comparison automatically; it would have been invisible
-- to a list, and an UPDATE that changed it while nulling `practiceId` would
-- have passed. The jsonb form is not a stylistic preference — it is the
-- difference between a guard that stays complete and one that decays.
--
-- ============================================================================
-- CONCURRENCY — WHY BOTH AN ADVISORY LOCK AND A UNIQUE INDEX
-- ----------------------------------------------------------------------------
-- Two transactions inserting for the same (practice, bucket) both read the same
-- "previous" row under READ COMMITTED, because neither can see the other's
-- uncommitted insert. Without serialization both would derive the same `seq`
-- and the same `balanceAfter`, and the ledger would silently lose a debit.
--
--   · `pg_advisory_xact_lock` serializes them, so the second WAITS and then
--     derives from the first. That is the mechanism that makes it CORRECT, and
--     it means callers do not need a retry loop.
--   · `ledger_entries_practiceId_bucket_seq_key` is the STRUCTURAL BACKSTOP. If
--     the lock is ever wrong — a hash collision routes two different practices
--     to one lock (harmless, just slower), a future edit drops the PERFORM line,
--     someone inserts through a path that skips the trigger — the unique index
--     turns a silent double-spend into a loud constraint violation.
--
-- The lock alone would be a convention held in one line of plpgsql. The unique
-- alone would make correct concurrent inserts fail and need retries. Both is
-- the shape where the fast path is correct and the failure path is loud.
--
-- ============================================================================
-- ORDER BY seq, NEVER BY createdAt
-- ----------------------------------------------------------------------------
-- `createdAt` defaults to `CURRENT_TIMESTAMP`, which is TRANSACTION START time
-- in Postgres — two rows written in one transaction share it exactly, and two
-- rows in different transactions can share it by coincidence. `seq` is the
-- ledger's order. Any reader that sorts by `createdAt` will eventually read a
-- balance history in the wrong order and see it as a data corruption.
-- ============================================================================

CREATE TABLE "ledger_entries" (
    "id"                 TEXT   NOT NULL,

    -- NULLABLE + SetNull, per the S4c financial-record rule above. NOT NULL at
    -- INSERT is enforced by the trigger, which is the only place that can tell
    -- an insert apart from a later detach.
    "practiceId"         TEXT,
    -- Tombstone. Survives the practice row itself, so "whose money was this"
    -- stays answerable after an account deletion. Derived by the trigger from
    -- `practiceId`, so it cannot be set to something else.
    "practiceIdSnapshot" TEXT   NOT NULL,

    "bucket"             TEXT   NOT NULL,
    "kind"               TEXT   NOT NULL,

    -- SIGNED micro-dollars. The balance is the running sum, so a debit is a
    -- negative amount rather than a positive number with a direction flag.
    "amountMicroUsd"     BIGINT NOT NULL,

    -- DATABASE-OWNED. Both are overwritten by `ledger_entries_derive()` on
    -- every insert; the DEFAULTs exist only so a Prisma caller need not send a
    -- value it is not allowed to choose. If the trigger were ever dropped these
    -- would read 0 and 0 — loudly wrong rather than quietly plausible, which is
    -- the direction a placeholder default should fail in.
    "balanceAfter"       BIGINT NOT NULL DEFAULT 0,
    "seq"                BIGINT NOT NULL DEFAULT 0,

    -- Optional, globally unique. An append-only table cannot delete a duplicate,
    -- so idempotency matters MORE here than in a mutable table, not less.
    -- NULLs are distinct in a btree unique, so rows without a key never collide.
    "idempotencyKey"     TEXT,

    "note"               TEXT,
    "createdAt"          TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ledger_entries_pkey" PRIMARY KEY ("id")
);

-- The (practice, bucket) sequence. Doubles as the index the derive trigger's
-- `ORDER BY seq DESC LIMIT 1` reads, and as the index `ON DELETE SET NULL`
-- needs when a practice is deleted.
CREATE UNIQUE INDEX "ledger_entries_practiceId_bucket_seq_key"
    ON "ledger_entries" ("practiceId", "bucket", "seq");

CREATE UNIQUE INDEX "ledger_entries_idempotencyKey_key"
    ON "ledger_entries" ("idempotencyKey");

ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_practiceId_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON UPDATE CASCADE ON DELETE SET NULL;

-- ── Closed vocabularies. A new bucket or kind is a MIGRATION, and that refusal
--    is the feature: an undeclared bucket would be a balance nobody sums.
ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_bucket_vocabulary"
    CHECK ("bucket" IN ('paid', 'promo'));

ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_kind_vocabulary"
    CHECK ("kind" IN ('grant', 'topup', 'usage', 'refund', 'adjustment'));

-- ── Sign rules for the three kinds whose direction is not in doubt. `refund`
--    and `adjustment` are deliberately unconstrained — see the header.
ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_kind_sign"
    CHECK (
        ("kind" = 'usage' AND "amountMicroUsd" <= 0)
     OR ("kind" = 'topup' AND "amountMicroUsd" >  0)
     OR ("kind" = 'grant' AND "amountMicroUsd" >  0)
     OR ("kind" IN ('refund', 'adjustment'))
    );

-- Backstop on the derivation: the trigger always produces seq >= 1, so a 0 here
-- means the trigger did not run.
ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_seq_positive"
    CHECK ("seq" > 0);

-- The tombstone must agree with the live pointer while the pointer exists. It
-- is derived, so this can only fail if something wrote around the trigger.
ALTER TABLE "ledger_entries"
    ADD CONSTRAINT "ledger_entries_snapshot_agrees"
    CHECK ("practiceId" IS NULL OR "practiceId" = "practiceIdSnapshot");

-- ============================================================================
-- THE DERIVATION TRIGGER
-- ============================================================================
CREATE OR REPLACE FUNCTION ledger_entries_derive() RETURNS trigger AS $fn$
DECLARE
    prev_seq     BIGINT;
    prev_balance BIGINT;
BEGIN
    -- An INSERT must name its practice. `practiceId` is nullable ONLY so that
    -- ON DELETE SET NULL can detach a row later; it is not a legal insert value.
    IF NEW."practiceId" IS NULL THEN
        RAISE EXCEPTION
            'ledger_entries_insert_requires_practice: a ledger row must name its practice at INSERT time. practiceId is nullable only so a practice deletion can detach the row afterwards (S4c).'
            USING ERRCODE = '23502';
    END IF;

    -- Serialize per (practice, bucket) so the read of the previous row and the
    -- write of this one cannot interleave. Transaction-scoped: released on
    -- COMMIT or ROLLBACK, never leaked.
    PERFORM pg_advisory_xact_lock(
        hashtext('ledger_entries'),
        hashtext(NEW."practiceId" || ':' || NEW."bucket")
    );

    SELECT e."seq", e."balanceAfter"
      INTO prev_seq, prev_balance
      FROM "ledger_entries" e
     WHERE e."practiceId" = NEW."practiceId"
       AND e."bucket"     = NEW."bucket"
     ORDER BY e."seq" DESC
     LIMIT 1;

    -- Unconditional. Whatever the caller sent is discarded — the caller does
    -- not get an opinion about the balance.
    NEW."seq"                := COALESCE(prev_seq, 0) + 1;
    NEW."balanceAfter"       := COALESCE(prev_balance, 0) + NEW."amountMicroUsd";
    NEW."practiceIdSnapshot" := NEW."practiceId";

    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

CREATE TRIGGER "ledger_entries_derive_before_insert"
    BEFORE INSERT ON "ledger_entries"
    FOR EACH ROW EXECUTE FUNCTION ledger_entries_derive();

-- ============================================================================
-- THE APPEND-ONLY TRIGGERS
-- ============================================================================
CREATE OR REPLACE FUNCTION ledger_entries_append_only() RETURNS trigger AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'ledger_entries_append_only: DELETE is refused on ledger_entries. The ledger is append-only (SPEC §2.1) — a correction is another row, never an erasure.'
            USING ERRCODE = 'P0001';
    END IF;

    -- THE ONE PERMITTED UPDATE: the S4c detach, and nothing else. Every other
    -- column is compared wholesale via jsonb so that a column added later is
    -- covered without anybody remembering to add it here.
    IF OLD."practiceId" IS NOT NULL
       AND NEW."practiceId" IS NULL
       AND (to_jsonb(NEW) - 'practiceId') = (to_jsonb(OLD) - 'practiceId')
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'ledger_entries_append_only: UPDATE is refused on ledger_entries. The ledger is append-only (SPEC §2.1); the only permitted update is ON DELETE SET NULL detaching practiceId, with every other column unchanged.'
        USING ERRCODE = 'P0001';
END;
$fn$ LANGUAGE plpgsql;

CREATE TRIGGER "ledger_entries_append_only_before_update"
    BEFORE UPDATE ON "ledger_entries"
    FOR EACH ROW EXECUTE FUNCTION ledger_entries_append_only();

CREATE TRIGGER "ledger_entries_append_only_before_delete"
    BEFORE DELETE ON "ledger_entries"
    FOR EACH ROW EXECUTE FUNCTION ledger_entries_append_only();

-- ⚠️ TRUNCATE FIRES NEITHER OF THE ABOVE. Row-level triggers do not see it and
-- it is not a DELETE — so a table protected only by BEFORE DELETE can still be
-- emptied in one statement. This is the statement-level trigger that closes it,
-- and it is the arm most likely to be left out.
CREATE OR REPLACE FUNCTION ledger_entries_no_truncate() RETURNS trigger AS $fn$
BEGIN
    RAISE EXCEPTION
        'ledger_entries_append_only: TRUNCATE is refused on ledger_entries. TRUNCATE bypasses row-level DELETE triggers, which is exactly why this statement-level trigger exists.'
        USING ERRCODE = 'P0001';
END;
$fn$ LANGUAGE plpgsql;

CREATE TRIGGER "ledger_entries_append_only_before_truncate"
    BEFORE TRUNCATE ON "ledger_entries"
    FOR EACH STATEMENT EXECUTE FUNCTION ledger_entries_no_truncate();

-- ============================================================================
-- THE TABLE STARTS EMPTY, AND THAT IS ASSERTED RATHER THAN ASSUMED.
-- A migration that half-ran and reported success is the failure AGENTS.md rule
-- 8 names; here the only thing to assert is that nothing pre-existed under this
-- name and that every object this migration promises actually exists.
-- ============================================================================
DO $verify$
DECLARE
    n_rows     BIGINT;
    n_triggers INT;
    n_checks   INT;
BEGIN
    SELECT count(*) INTO n_rows FROM "ledger_entries";
    IF n_rows <> 0 THEN
        RAISE EXCEPTION 'B5: ledger_entries is not empty (% rows) immediately after creation', n_rows;
    END IF;

    SELECT count(*) INTO n_triggers
      FROM pg_trigger
     WHERE tgrelid = '"ledger_entries"'::regclass
       AND NOT tgisinternal;
    IF n_triggers <> 4 THEN
        RAISE EXCEPTION 'B5: expected 4 triggers on ledger_entries, found %', n_triggers;
    END IF;

    SELECT count(*) INTO n_checks
      FROM pg_constraint
     WHERE conrelid = '"ledger_entries"'::regclass
       AND contype = 'c'
       AND conname LIKE 'ledger_entries_%';
    IF n_checks <> 5 THEN
        RAISE EXCEPTION 'B5: expected 5 named CHECK constraints on ledger_entries, found %', n_checks;
    END IF;
END;
$verify$;
