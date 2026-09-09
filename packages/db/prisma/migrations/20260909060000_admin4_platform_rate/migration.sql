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
    "effectiveFrom" TIMESTAMPTZ(6) NOT NULL,
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
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_margin_bounds" CHECK (
      "marginDenominator" > 0
  AND "marginNumerator"   > 0
  AND "marginNumerator" >= "marginDenominator"
  AND "marginNumerator" <= 5 * "marginDenominator"
);

-- The previous value is present or absent as a PAIR — a half-recorded history
-- is worse than none, because it reads as a complete one.
ALTER TABLE "platform_rates" ADD CONSTRAINT "platform_rates_previous_pair" CHECK (
  ("previousNumerator" IS NULL) = ("previousDenominator" IS NULL)
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
