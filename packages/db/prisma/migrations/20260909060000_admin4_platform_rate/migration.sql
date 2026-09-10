-- ADMIN-4 — THE PLATFORM MARGIN BECOMES A ROW, ruling #178.
--
-- ⚠️ THE FAILURE THIS CLOSES IS ALREADY SHIPPED. `packages/ai/src/price-table.ts`
-- computed `costMicro * 3n / 2n` and `billing-charge.ts` stamped the literal
-- string '3/2' onto every ledger row. Both landed 2026-08-11 in B6 (cac9db7a),
-- THREE WEEKS BEFORE ruling #178 was written to forbid exactly it: "a rate
-- nobody can change without a deploy, and — worse — a rate with no audit row
-- saying who changed it."
--
-- ⚠️ AND IT WAS HARMLESS ONLY BY ACCIDENT OF CONFIGURATION: `BILLING_ENFORCED`
-- appears nowhere in the production compose file, and the writer additionally
-- calls `assertProdDatabase()`. Neither is a decision anybody recorded about
-- the margin; both are unrelated guards that happen to sit in front of it.
--
-- ⚠️ THE MARGIN IS AN EXACT RATIO IN INTEGERS. Never a float, never a NUMERIC
-- that a driver may hand back as a JS Number. `price-table.ts` states why:
-- `1.5` is exactly representable in binary64, but `cost * 1.5` is a Number, so
-- any cost above 2^53 micro-dollars silently loses precision. Two INTEGER
-- columns keep the arithmetic in `bigint` from the row to the ledger.

CREATE TABLE "platform_rates" (
    "id" TEXT NOT NULL,
    "marginNumerator" INTEGER NOT NULL,
    "marginDenominator" INTEGER NOT NULL,
    -- NULLABLE ON THE WAY IN — the BEFORE INSERT trigger fills it with the
    -- server's own clock and it is never null at rest. See the trigger.
    "effectiveFrom" TIMESTAMPTZ(6),
    "changedByUserId" TEXT,
    -- ⚠️ THE ACTOR SNAPSHOT, AND IT IS NOT REDUNDANT WITH THE FK.
    -- The FK detaches on user deletion (the house rule: audit rows DETACH, never
    -- delete). Detaching a rate change would erase WHO CHANGED THE PRICE, which
    -- is the half of #178 that is not about the rate at all. NOT NULL: the
    -- writer cannot omit it, and there is no seed row to exempt.
    "changedByLabel" TEXT NOT NULL,
    "previousNumerator" INTEGER,
    "previousDenominator" INTEGER,
    "note" TEXT,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "platform_rates_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "platform_rates_effectiveFrom_idx" ON "platform_rates"("effectiveFrom");

ALTER TABLE "platform_rates"
  ADD CONSTRAINT "platform_rates_changedByUserId_fkey"
  FOREIGN KEY ("changedByUserId") REFERENCES "users"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- ⚠️ A ZERO OR NEGATIVE DENOMINATOR IS A DIVISION FAULT, NOT A BAD SETTING, so
-- it is refused by the DATABASE rather than by whichever writer remembers.
-- The bounds are #178's own: >= 1.0 and <= 5.0. Expressed as a cross-multiply
-- so it stays integer arithmetic here too — `n >= d` is `n/d >= 1`, and
-- `n <= 5d` is `n/d <= 5`.
--
-- ⚠️ `5::bigint`, NOT `5` — ROUND 5, AND WITHOUT IT THE TWO ENCODINGS OF #178's
-- BOUNDS WERE NOT THE SAME RULE. `5 * "marginDenominator"` is int4*int4, and
-- `int4mul` RAISES rather than widening: measured on PG 16.15, every legal
-- margin with a denominator above 429,496,729 (= floor(int4max/5)) aborted with
-- `ERROR: integer out of range` — SQLSTATE 22003, raised in `int4mul`, naming
-- NEITHER the constraint nor the column — while the exported TypeScript mirror
-- `isUsableMargin` returned `true` for the identical pair. Measured:
-- 1500000000/1000000000 (exactly 1.5), 2000000000/500000000 (exactly 4.0) and
-- 429496730/429496730 (exactly 1.0) were all refused; 429496729/429496729 was
-- accepted.
--
-- It was a false-REJECTION band only, and that is provable rather than surveyed:
-- if `5*d` overflows then `5d > int4max >= n`, so every row that triggered it
-- would have satisfied the ceiling anyway. No out-of-bounds margin could ever
-- be admitted by it. But the whole product of ADMIN-4 is that a number is not
-- encoded twice in two places free to drift, and this file and
-- `price-table.ts:isUsableMargin` disagreed over a range of legal inputs.
-- ⚠️ AND A REFUSAL THAT NAMES NOTHING BREAKS THIS FILE'S OWN STANDARD — "a
-- refusal is evidence only when you know WHAT refused".
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_margin_bounds" CHECK (
      "marginDenominator" > 0
  AND "marginNumerator"   > 0
  AND "marginNumerator" >= "marginDenominator"
  AND "marginNumerator" <= 5::bigint * "marginDenominator"
);

-- The previous value is present or absent as a PAIR — a half-recorded history
-- is worse than none, because it reads as a complete one.
--
-- ⚠️ THIS CHECK, AND `previous_bounds` BELOW, ARE NOW BELT AND BRACES: the pair
-- is DERIVED by the BEFORE INSERT trigger and the caller has no opinion about
-- it (see `platform_rates_stamp_created`). They are kept, not deleted, because
-- a trigger `prisma migrate dev` cannot see is one regeneration from being
-- absent — and then these are the only thing left.
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_previous_pair" CHECK (
  ("previousNumerator" IS NULL) = ("previousDenominator" IS NULL)
);

-- ⚠️ THE ACTOR CANNOT BE BLANK — ROUND 4. `NOT NULL` does not stop `''`, so a
-- price change could be written with no recorded actor of any kind: measured,
-- `changedByLabel = ''` with `changedByUserId = NULL` was accepted. The column's
-- own comment claims "the writer cannot omit it"; NOT NULL alone did not deliver
-- that. Every other invariant here is enforced by the DATABASE precisely so it
-- does not depend on whichever writer remembers — the actor was the one that did.
--
-- ⚠️ AND ROUND 4 CLOSED `''` AND LEFT THE CLASS — ROUND 5. `btrim/1`'s DEFAULT
-- TRIM SET IS THE SPACE CHARACTER AND NOTHING ELSE. Measured on PG 16.15 against
-- round 4's constraint: `''` and `'   '` were refused BY NAME, and a TAB, a
-- `\n\r`, U+00A0 (no-break space), U+2007 (figure space) and U+3000
-- (ideographic space) were each ACCEPTED — a permanent, uncorrectable price
-- change whose only recorded actor is invisible, with `changedByUserId` NULL.
-- That is verbatim the state the paragraph above says is impossible.
--
-- ⚠️ THE OBVIOUS REPAIRS ALSO LEAVE THE CLASS OPEN, WHICH IS WHY THE SET IS
-- WRITTEN OUT. Measured on the same database: `btrim(x, E' \t\n\r')` ACCEPTS
-- U+00A0, and so does `x ~ '[^[:space:]]'` — POSIX `[:space:]` does not class
-- NBSP here, and `\S` behaves the same. `[[:graph:]]` accepts NBSP and rejects
-- U+3000. A locale-dependent character class is the wrong instrument for a
-- locale-independent invariant, so the blanks are ENUMERATED: the ASCII
-- controls, every Unicode space separator, the two line/paragraph separators,
-- and the zero-width/invisible formatting characters that render as nothing
-- without being classed as space anywhere.
--
-- Verified: all 24 of those inputs score 0 and are refused; `kasra@example.com`,
-- an accented Latin name, a Cyrillic name, a CJK name and a single letter all
-- score > 0 and are accepted. The positive controls matter as much as the
-- refusals — a constraint that refused every actor would score full marks here
-- and make the ADMIN-4 writer unusable.
--
-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ ROUND 6 — THE PARAGRAPH ABOVE IS SUPERSEDED: THE ENUMERATION CLOSED
-- INSTANCES AND LEFT THE CLASS, THE SAME SHAPE IT CRITICISES IN ROUND 4.
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Measured on PG 16.15 against round 5's enumerated trim set: 21 inputs were
-- ACCEPTED as the only recorded actor, each a single code point with
-- changedByUserId NULL — chr(1), chr(27), chr(127) (ASCII controls, which the
-- paragraph above claims are covered), U+200E/200F (LRM/RLM, category Cf —
-- the SAME category as the enumerated U+200B and U+FEFF), U+00AD, U+034F,
-- U+061C, U+180E, U+2061–2064, U+202A/202E, U+2066/2069, U+FE0F, U+E0020,
-- U+1D159 and U+2800. A trim set is an open list of "things that are blank";
-- nobody can finish writing it down.
--
-- So the rule is INVERTED to a class that is closed and DERIVED: the actor
-- must contain AT LEAST ONE LETTER OR DIGIT — Unicode general category L* or
-- Nd — rather than "must not be only blanks". Every control, format, space,
-- mark, symbol and punctuation code point fails it by construction, without
-- being named.
--
-- ⚠️ `COLLATE "und-x-icu"` IS WHAT MAKES IT LOCALE-INDEPENDENT, WHICH WAS
-- ROUND 5's OBJECTION TO A CHARACTER CLASS, AND THE OBJECTION WAS RIGHT FOR
-- libc. Postgres classifies regex characters by the COLLATION OF THE INPUT:
-- under libc "C" `[[:alnum:]]` is ASCII-only (measured: é, И and 王 all
-- false — a Cyrillic or CJK name would be refused and the writer stranded);
-- under a libc locale it is whatever glibc says. Under an ICU collation it is
-- ICU's `u_isalnum` — the Unicode Character Database's general category, the
-- same on every server. Measured on this image: é, И, 王, ١ (Arabic-Indic one)
-- true; U+200E, U+00AD, U+2800, U+E0020, '.', '²' false. `und-x-icu` exists
-- wherever Postgres was built with ICU: counted read-only 2026-09-10 on the
-- production and QA databases (1 each). On a server without ICU this migration
-- FAILS LOUDLY at this line, never silently.
--
-- ⚠️ KNOWN RESIDUAL, RECORDED RATHER THAN HIDDEN: the four Hangul fillers
-- U+115F, U+1160, U+3164 and U+FFA0 are general category Lo — Unicode classes
-- them as LETTERS — yet render as nothing (they are Default_Ignorable). A label
-- made ONLY of fillers is accepted. Postgres 16 exposes no Default_Ignorable
-- property, and closing them here would mean enumerating code points again —
-- the move this block exists to stop. `check-platform-rates-invariants.sh`
-- reports them as a residual on every run so the gap stays visible.
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_actor_present" CHECK (
  ("changedByLabel" COLLATE "und-x-icu") ~ '[[:alnum:]]'
);

-- ⚠️ AND THE PREVIOUS PAIR OBEYS THE SAME BOUNDS AS THE CURRENT ONE — ROUND 4.
-- `previous_pair` checked only that the two are NULL together, so `0/0` and
-- `-7/-1` were both accepted. The margin CHECK's own comment names this hazard
-- one paragraph earlier — "A ZERO OR NEGATIVE DENOMINATOR IS A DIVISION FAULT,
-- NOT A BAD SETTING" — and it was applied to the current value and not to the
-- recorded previous one, which exists to BE READ ("so the history reads without
-- a self-join"). A `0/0` previous value reads as a complete history too.
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_previous_bounds" CHECK (
  "previousNumerator" IS NULL OR (
        "previousDenominator" > 0
    AND "previousNumerator"   > 0
    AND "previousNumerator" >= "previousDenominator"
    -- `5::bigint` for the same reason as the current pair above — the same
    -- int4 overflow reproduced here verbatim (previous 430000000/430000000 ->
    -- `integer out of range`).
    AND "previousNumerator" <= 5::bigint * "previousDenominator"
  )
);

-- ⚠️ FORWARD-ONLY IS ENFORCED HERE, NOT MERELY STATED.
--
-- The first version of this migration called the column "FORWARD-ONLY BY
-- POLICY" and the pricing comment claimed anchoring the READ to the usage
-- instant achieved it. IT DOES NOT. Anchoring stops the RUN clock re-pricing a
-- backlog; it says nothing about a row whose `effectiveFrom` precedes its own
-- insertion. A backdated row is selected by `effectiveFrom <= at` exactly like
-- any other, so inserting `{effectiveFrom: last month, 5/1}` today RE-PRICES
-- every uncharged visit since then, at a stamp that resolves cleanly and looks
-- correct.
--
-- A rate takes effect when it is set or later. Never before.
--
-- ⚠️ AND "SET" MEANS THE **INSERT STATEMENT**, NOT THE COMMIT — ROUND 5, RECORDED
-- BECAUSE IT LOOKS LIKE A DEFECT AND IS NOT CLOSABLE HERE.
--
-- `clock_timestamp()` is evaluated inside the INSERT; the row becomes readable
-- at COMMIT. Between those two instants the row's own `effectiveFrom` is already
-- in the past while no reader can see it. Measured on PG 16.15: a writer holding
-- its transaction open 5s stamped `effectiveFrom = 15:18:13.077` and committed
-- at `15:18:18.084`; the SAME `marginAt` query for one fixed usage instant
-- inside that window returned the OLD rate during the transaction and the NEW
-- rate afterwards. The consequence is not an over-charge — under READ COMMITTED
-- the charge serialized before the commit, so applying the old rate is the
-- defensible answer — it is that `platform_rates` afterwards asserts a rate was
-- in effect at an instant no reader could have seen it.
--
-- ⚠️ NO SPELLING AT THIS LINE CLOSES IT, and that is the whole reason nothing
-- here changed. Postgres does not expose commit time to a column. `now()` is
-- strictly worse (transaction-start — the very window round 3 closed). The only
-- remaining spelling is a GUESSED future offset, which is exactly what round 4
-- rejected because it stranded the writer completely. Any real closure is
-- READER-side (a shared advisory lock between the writer and `marginAt`, or a
-- visibility watermark) and lives in ordinary TypeScript that can be edited any
-- day; a migration cannot be. The floor of the window is the writing
-- transaction's commit latency, and a writer supplying its own FUTURE
-- `effectiveFrom` avoids it completely — measured, the divergence disappears at
-- `clock_timestamp() + 30s`.
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_forward_only" CHECK (
  "effectiveFrom" >= "createdAt"
);

-- ⚠️ NO SEED ROW IS INSERTED HERE, AND THAT IS THE POINT.
--
-- Seeding 3/2 would make the migration itself the thing that decides the rate,
-- with no actor and no note — the same defect one layer up, wearing a
-- migration's clothes. The read path FAILS CLOSED on an empty table: it
-- refuses the charge with `no_margin_rate` rather than defaulting to 3/2.
--
-- ⚠️ SO APPLYING THIS MIGRATION ALONE STOPS NO BILLING AND STARTS NONE.
-- `BILLING_ENFORCED` is absent from the production compose, so the charge path
-- does not run; the FAILURE-COST OBSERVER does run and will now record
-- `no_margin_rate` instead of a cost, which is the honest reading until an
-- operator sets the rate through the ADMIN-4 surface.

-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ ROUND 2 — THE FORWARD-ONLY CHECK ABOVE CONSTRAINS A HONEST WRITER ONLY.
-- ═══════════════════════════════════════════════════════════════════════════
--
-- `platform_rates_forward_only` compares two columns THE WRITER SUPPLIES.
-- Prisma generates `createdAt?: Date | string` for a `@default(now())` field,
-- so a caller may pass BOTH:
--
--     { effectiveFrom: '2026-08-01', createdAt: '2026-08-01', 5/1 }
--
-- — the CHECK is satisfied (equal), the bounds pass, and `marginAt` then prices
-- every uncharged August visit at 5x cost. And an `UPDATE` re-prices
-- retroactively without touching either column at all.
--
-- Round 1 closed the INSTANCE it was shown (a wall-clock read) and left the
-- CLASS. Two triggers close it, both copied in shape from `ledger_entries`,
-- which this repository already protects exactly this way.

-- 1 — `createdAt` IS SERVER-AUTHORITATIVE, AND SO IS THE PREVIOUS PAIR. A
--     supplied value is overwritten, not rejected: refusing would break the
--     ordinary `create()` that omits it, and the point is that the column means
--     "when the server saw this row". Round 5 extends the same rule to
--     `previousNumerator`/`previousDenominator` — see the derivation below.
CREATE OR REPLACE FUNCTION platform_rates_stamp_created() RETURNS trigger AS $fn$
BEGIN
    -- ═══════════════════════════════════════════════════════════════════════
    -- ⚠️ ROUND 6 — THREE WAYS THE DERIVED PREVIOUS PAIR COULD STILL BE FALSE,
    -- each measured on PG 16 against round 5's trigger, each permanent (UPDATE,
    -- DELETE and TRUNCATE are refused, so a false row cannot be corrected).
    -- ═══════════════════════════════════════════════════════════════════════
    --
    -- (a) ABOVE READ COMMITTED THE LOCK SERIALIZES NOTHING. The SELECT below
    --     reads the TRANSACTION snapshot, taken at the INSERT's start — before
    --     the lock wait — and never refreshed. Measured: seed 3/2; B inserts
    --     2/1 and holds its transaction; A runs `BEGIN ISOLATION LEVEL
    --     REPEATABLE READ; INSERT 4/1; COMMIT` with the INSERT as its only
    --     statement. A recorded previous = 3/2; the rate in effect at A's
    --     createdAt was B's 2/1. SERIALIZABLE recorded the same, with NO 40001:
    --     a serial order A-before-B is consistent with every read, because the
    --     anchor is wall-clock time and visibility follows serialization order.
    --     Ruling #269 measured this exact shape on the last-owner guard and
    --     refuses BY NAME; this is the same refusal.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION
          'platform_rates: cannot derive the previous rate at isolation level % — this insert must run at READ COMMITTED; a snapshot taken before the platform_rates lock never refreshes, so the previous pair would be read from before a competing rate committed (ADMIN-4, ruling #269)',
          current_setting('transaction_isolation')
          USING ERRCODE = '0A000';
    END IF;

    -- (b) THE LOCK IS TAKEN **BEFORE** `createdAt` IS STAMPED. Round 5 stamped
    --     first and locked afterwards, so the stamp order and the lock order
    --     could disagree: a writer stamped at t1 could lose the lock to one
    --     stamped at t2 > t1, which then derived without seeing t1's row even
    --     though t1's row was in effect at t2 by the derivation's own
    --     predicate. Measured at the DEFAULT isolation with honest writers:
    --     16 writers x 300 inserts → 2–8 of 4800 rows false; 2 x 3000 → 1–2
    --     of 6000. Moving this one line above the stamp: 0, 0, 0 and 0.
    --     With the lock first, every later stamp is taken AFTER the earlier
    --     writer committed, and READ COMMITTED gives the SELECT below a fresh
    --     snapshot that contains it. Transaction-scoped; released at COMMIT.
    PERFORM pg_advisory_xact_lock(hashtext('platform_rates'), 0);

    -- (c) THE NAMES ARE PINNED. Unqualified, `platform_rates` resolved
    --     through the CALLER's search_path, where `pg_temp` comes first for
    --     relations — measured: a session TEMP table named `platform_rates`
    --     supplied the previous pair (5/1 recorded; the real latest was 4/1),
    --     needing only the default TEMP privilege. And `clock_timestamp()`
    --     unqualified lost to a `public.clock_timestamp()` under
    --     `SET LOCAL search_path = public, pg_catalog`, back-dating a rate to
    --     2026-08-01 with every trigger still enabled. So the table is
    --     schema-qualified, the clock is `pg_catalog.`-qualified, and every
    --     function in this file carries `SET search_path = pg_catalog, public,
    --     pg_temp` — `pg_temp` LAST and explicit, because the verifier measured
    --     that `pg_catalog, public` alone still let the TEMP table win: an
    --     unlisted pg_temp is searched FIRST for relations.

    -- ⚠️ `clock_timestamp()`, NOT `now()`. `now()` is TRANSACTION START time, so
    -- a writer that opens a transaction, does other work, then inserts, stores a
    -- rate "effective" earlier than the moment it was actually written — by
    -- exactly the transaction's duration. Measured on a real Postgres: 3.011s of
    -- retroactive window from a `pg_sleep(3)` before the INSERT. The admin
    -- writer #178 calls for will run inside a transaction.
    NEW."createdAt" := pg_catalog.clock_timestamp();
    -- ⚠️ NULL MEANS "EFFECTIVE IMMEDIATELY", AND WITHOUT IT ROUND 3's FIX
    -- STRANDED THE WRITER COMPLETELY.
    --
    -- Round 3 stamped `createdAt` with `clock_timestamp()` to close a measured
    -- 3.011s retroactive window. Correct — and it made `effectiveFrom = now()`
    -- REFUSED BY NINE MICROSECONDS, because `now()` is transaction-start and the
    -- stamp is statement-time. Measured on a real PG 16.13: every spelling an
    -- honest writer has — `now()`, `CURRENT_TIMESTAMP`, `statement_timestamp()`,
    -- even `clock_timestamp()` itself — was refused, and only a GUESSED future
    -- offset landed (+1ms refused, +10ms accepted). Prisma sends a
    -- client-computed `new Date()`, always earlier still, and cannot send a raw
    -- SQL expression through `create()` at all.
    --
    -- So the writer #178 calls for could not have set a rate AT ALL, and the
    -- refusal would have read like an attack being blocked. Fail-closed is the
    -- rule; STRANDING is not, and this was a strand.
    --
    -- NULL is the one spelling that cannot be in the past. The server decides
    -- what "now" means, which is the property fix C was really after.
    IF NEW."effectiveFrom" IS NULL THEN
        NEW."effectiveFrom" := NEW."createdAt";
    END IF;
    IF NEW."effectiveFrom" < NEW."createdAt" THEN
        RAISE EXCEPTION
          'platform_rates: effectiveFrom % precedes insertion at % — a rate takes effect when it is set or later, never before (ADMIN-4, #178)',
          NEW."effectiveFrom", NEW."createdAt"
          USING ERRCODE = 'check_violation';
    END IF;

    -- ═══════════════════════════════════════════════════════════════════════
    -- ⚠️ ROUND 5 — `previous*` WAS AN UNCHECKED CALLER CLAIM, AND THE PRIOR ART
    -- THIS FILE SAYS IT COPIED DERIVES EVERY DERIVABLE COLUMN INSTEAD.
    -- ═══════════════════════════════════════════════════════════════════════
    --
    -- Measured on PG 16.15 against round 4's table, four inserts in order:
    --
    --   R1 3/2  (no pair)      R2 4/1 claiming previous 5/1   -- actual: 3/2
    --   R3 2/1  (no pair)      R4 3/1 claiming previous 1/1   -- actual: 2/1
    --
    -- ALL FOUR ACCEPTED. R2 permanently records that the platform margin went
    -- 5.0 -> 4.0 when it went 1.5 -> 4.0; R3 is the SECOND change and is
    -- byte-indistinguishable from a first row. And because UPDATE, DELETE and
    -- TRUNCATE are all refused, the false history is UNCORRECTABLE in band —
    -- correcting it means deliberately disabling this table's central guarantee.
    --
    -- ⚠️ AND IT IS NOT A WRITER-DISCIPLINE PROBLEM, WHICH IS WHY NO WRITER COULD
    -- HAVE FIXED IT. Two HONEST writers, each reading the current rate and
    -- recording it, falsify each other: nothing serialized the read of "what it
    -- is now" against the write of "what it is now". `ledger_entries_derive()`
    -- takes `pg_advisory_xact_lock` for exactly this reason and states the rule
    -- this trigger now follows — *"the caller does not get an opinion"*.
    --
    -- ⚠️ THE ANCHOR IS `createdAt`, NOT `effectiveFrom`, AND THE DIFFERENCE IS
    -- THE WHOLE REASON THIS DERIVATION IS PERMANENT. `previous*` means **the
    -- margin in effect at the instant this change was WRITTEN** — #178's audit
    -- row is "actor, timestamp, old -> new", and "old" is what the operator was
    -- changing away from when they made the change.
    --
    -- Anchored to `createdAt` the answer can never be falsified by a later row:
    -- `platform_rates_forward_only` guarantees every later row has
    -- `effectiveFrom >= its own createdAt > this row's createdAt`, so no future
    -- insert can ever fall inside `effectiveFrom <= NEW."createdAt"`.
    -- Anchored to `effectiveFrom` it COULD be: a row scheduled +30d, then a row
    -- inserted afterwards effective +1d, retroactively changes which rate the
    -- scheduled row supersedes — correct when written, permanently wrong later,
    -- in a table that cannot be corrected.
    --
    -- ⚠️ THE LOCK IS ALREADY HELD — taken at the top of this function, before
    -- the stamp. See (b) there for why it cannot live here any more.
    --
    -- ⚠️ `ORDER BY "effectiveFrom" DESC, "createdAt" DESC` IS LOAD-BEARING and
    -- is `marginAt`'s own order. `ORDER BY "createdAt" DESC` alone records the
    -- most recently WRITTEN row, which is not the one in effect when a row was
    -- scheduled ahead: A 3/2; S 5/1 effective +2s; B 2/1; then C after S took
    -- effect — `createdAt DESC` records B (2/1), `marginAt` says S (5/1).
    SELECT p."marginNumerator", p."marginDenominator"
      INTO NEW."previousNumerator", NEW."previousDenominator"
      FROM "public"."platform_rates" p
     WHERE p."effectiveFrom" <= NEW."createdAt"
     ORDER BY p."effectiveFrom" DESC, p."createdAt" DESC
     LIMIT 1;
    -- Unconditional: `SELECT ... INTO` with no matching row sets BOTH targets to
    -- NULL, so the pair is NULL exactly when no margin was in effect at the
    -- write instant, and whatever the caller sent is discarded either way.

    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql
  SET search_path = pg_catalog, public, pg_temp;

CREATE TRIGGER "platform_rates_stamp_created_before_insert"
    BEFORE INSERT ON "platform_rates"
    FOR EACH ROW EXECUTE FUNCTION platform_rates_stamp_created();

-- 2 — APPEND-ONLY. A rate history that can be edited is not a history, and the
--     whole product of #178 is "an audit row saying who changed it". An UPDATE
--     is how that row becomes a lie without anything appearing to change.
CREATE OR REPLACE FUNCTION platform_rates_append_only() RETURNS trigger AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
          'platform_rates: DELETE is refused. A rate history that can be erased is not a history (ADMIN-4, #178).'
          USING ERRCODE = 'P0001';
    END IF;

    -- ⚠️ THE ONE PERMITTED UPDATE — AND WITHOUT IT THIS TRIGGER BLOCKS USER
    -- DELETION ENTIRELY. `changedByUserId` carries `ON DELETE SET NULL`, so
    -- removing a user fires an UPDATE here; a blanket refusal would make the
    -- rate history hold accounts hostage. `ledger_entries` documents this exact
    -- hole one table over and solves it the same way.
    --
    -- Every other column is compared WHOLESALE via jsonb, so a column added
    -- later is covered without anybody remembering to come back here.
    IF OLD."changedByUserId" IS NOT NULL
       AND NEW."changedByUserId" IS NULL
       AND (to_jsonb(NEW) - 'changedByUserId') = (to_jsonb(OLD) - 'changedByUserId')
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
      'platform_rates is append-only: a rate change is a NEW ROW (ADMIN-4, #178). The only permitted update is ON DELETE SET NULL detaching changedByUserId, with every other column unchanged.'
      USING ERRCODE = 'P0001';
END;
$fn$ LANGUAGE plpgsql
  SET search_path = pg_catalog, public, pg_temp;

CREATE TRIGGER "platform_rates_no_update"
    BEFORE UPDATE ON "platform_rates"
    FOR EACH ROW EXECUTE FUNCTION platform_rates_append_only();

CREATE TRIGGER "platform_rates_no_delete"
    BEFORE DELETE ON "platform_rates"
    FOR EACH ROW EXECUTE FUNCTION platform_rates_append_only();

-- ⚠️ 3 — AND `TRUNCATE`, WHICH FIRES NEITHER OF THE ABOVE.
--
-- Row-level triggers do not see TRUNCATE. Measured on a real Postgres 16:
-- DELETE, UPDATE, a backdated INSERT, `INSERT … ON CONFLICT DO UPDATE` and a
-- `COPY` were each refused BY NAME — and `TRUNCATE "platform_rates";` emptied
-- the table, 2 rows to 0, silently.
--
-- ⚠️ THE PRIOR ART THIS MIGRATION SAYS IT COPIED HAS THIS ARM, AND ITS COMMENT
-- IS THE WARNING I WALKED PAST: `ledger_entries_append_only_before_truncate` —
-- *"TRUNCATE FIRES NEITHER OF THE ABOVE … it is the arm most likely to be left
-- out."* It was.
--
-- The cost is not abstract: truncating this table makes every already-written
-- `ledger_entries.pricing.platformRateId` unresolvable, which is verbatim the
-- §2.5 declaration's own failure criterion.
CREATE OR REPLACE FUNCTION platform_rates_no_truncate() RETURNS trigger AS $fn$
BEGIN
    RAISE EXCEPTION
      'platform_rates: TRUNCATE is refused. The rate history is the product of #178 — an audit row saying who changed it — and every ledger row references it by id.'
      USING ERRCODE = 'P0001';
END;
$fn$ LANGUAGE plpgsql
  SET search_path = pg_catalog, public, pg_temp;

CREATE TRIGGER "platform_rates_no_truncate"
    BEFORE TRUNCATE ON "platform_rates"
    FOR EACH STATEMENT EXECUTE FUNCTION platform_rates_no_truncate();

-- ⚠️ 4 — THE MIGRATION VERIFIES ITSELF, because `prisma migrate dev` cannot see
-- triggers at all and would regenerate this file without them. This diff quotes
-- `scripts/check-ledger-append-only.sh` TWICE — *"prisma migrate dev … silently
-- omits them … every test green. The only observable difference is that money
-- can now be edited"* — and then did not add the guard that quote argues for.
-- Both cited prior-art migrations carry one; this is theirs.
DO $verify$
DECLARE
    n_trig   int;
    n_check  int;
    n_pinned int;
BEGIN
    -- ⚠️ ROUND 6 — EVERY FUNCTION HERE RUNS WITH A PINNED search_path. Without
    -- it a caller's TEMP table or a shadowing `public.clock_timestamp()` rewrote
    -- the derived history (see `platform_rates_stamp_created`). Asserted by
    -- identity (`regprocedure`), so a same-named function elsewhere cannot be
    -- counted in its place.
    SELECT count(*) INTO n_pinned
      FROM pg_proc p
     WHERE p.oid IN ('platform_rates_stamp_created()'::regprocedure,
                     'platform_rates_append_only()'::regprocedure,
                     'platform_rates_no_truncate()'::regprocedure)
       AND p.proconfig @> ARRAY['search_path=pg_catalog, public, pg_temp'];
    IF n_pinned <> 3 THEN
        RAISE EXCEPTION 'platform_rates: expected 3 functions with a pinned search_path, found %', n_pinned;
    END IF;

    SELECT count(*) INTO n_trig
      FROM pg_trigger t
     -- ⚠️ `regclass`, NOT `relname` — ROUND 4. `relname` has no namespace
     -- filter, so ANY same-named relation in another schema is counted too.
     -- Measured: with a decoy `archive.platform_rates` carrying one trigger,
     -- this block counted 4 while `public.platform_rates` had 3 — and CERTIFIED
     -- a table that had lost its TRUNCATE arm. The right question asked of the
     -- wrong universe. The prior art this copies uses regclass for this reason.
     WHERE t.tgrelid = '"platform_rates"'::regclass AND NOT t.tgisinternal;
    IF n_trig <> 4 THEN
        RAISE EXCEPTION 'platform_rates: expected 4 triggers, found %', n_trig;
    END IF;

    SELECT count(*) INTO n_check
      FROM pg_constraint con
     WHERE con.conrelid = '"platform_rates"'::regclass AND con.contype = 'c';
    IF n_check <> 5 THEN
        RAISE EXCEPTION 'platform_rates: expected 5 CHECK constraints, found %', n_check;
    END IF;
END;
$verify$;
