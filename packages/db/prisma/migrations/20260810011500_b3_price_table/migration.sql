-- ============================================================================
-- FOUNDATION B3 — THE VERSIONED PRICE TABLE
-- ----------------------------------------------------------------------------
-- SPEC §2.2 (a versioned price-table snapshot), §4.4 (integer micro-dollars),
-- §4.5 (PROVENANCE is a required column, not a comment).
--
-- WHAT THIS MIGRATION CLAIMS, AND WHAT IT DOES NOT
--
--   It claims: these are the rates the four vendors PUBLISHED on 2026-08-04,
--   recorded with the page they came from and the day it was read, in a shape
--   where a later rate change cannot re-price an earlier call.
--
--   It does NOT claim that anything is billed from them. No code reads this
--   table for money yet — the meter still prices from `packages/ai/src/pricing.ts`
--   and `api-usage.ts`'s `PRICING`, and repointing it is B4/B6. Both in-code
--   surfaces are deliberately LEFT ALONE: SPEC §4.5 says changing them now would
--   silently re-base a year of historical `ai_calls` comparisons for no benefit.
--
--   It does NOT claim to be complete. `nova-3-medical` — THE MODEL THAT ACTUALLY
--   RUNS BY DEFAULT (`deepgram-batch.ts:24`) — IS ABSENT ON PURPOSE. Its only
--   public figure is an UNDATED announcement post, which SPEC §4.5 disqualifies
--   by name from a `published` provenance. Seeding it anyway would be the exact
--   failure this table exists to prevent: a number in a billing system that
--   nobody can trace to a source. It lands when the vendor answers
--   `docs/foundation/B3-deepgram-rate-request.md`, with `invoice` or `console`
--   provenance. THE TABLE IS 2 OF 3 DEEPGRAM RATES AND SAYS SO.
--
-- WHY effectiveFrom IS THE READ-DATE AND NOT '-infinity'
--
--   We know these rates held on 2026-08-04, because that is the day they were
--   read off the vendors' pages. We do not know when they took effect. Backdating
--   them to the beginning of time would assert something nobody verified, so a
--   lookup for an instant before 2026-08-04 finds NOTHING and the caller refuses.
--   That costs nothing: ruling 79 puts the meter's provenance regime at B0-a
--   (2026-08-08) and B9's reconciliation scope with it, both after this date.
--
-- THE THREE CONSTRAINTS BELOW ARE THE POINT OF THE TABLE
--
--   1. `price_rates_no_overlap` makes "two rates in effect at once" UNREPRESENTABLE.
--      Without it, versioning is a convention, and conventions are kept by hand.
--   2. `price_rates_published_needs_source` makes a sourceless `published` rate
--      unrepresentable — SPEC §4.5's provenance requirement, enforced.
--   3. `price_rates_unit_quantity_matches_type` pins each unit to its one legal
--      denominator, so a rate can never quietly mean something nobody declared.
--
--   ⚠️ None of the three is expressible in `schema.prisma`. All three are
--   declared beside the model in the `schema.prisma:1700` style, per AGENTS.md
--   rule 7 — a raw constraint the schema does not mention is drift.
-- ============================================================================

-- `price_rates_no_overlap` is a GiST exclusion constraint mixing equality
-- columns with a range. Plain btree cannot do that; btree_gist teaches GiST the
-- equality operators for scalar types.
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE "price_rates" (
    "id"            TEXT         NOT NULL,
    "provider"      TEXT         NOT NULL,
    "modelName"     TEXT         NOT NULL,
    "deliveryMode"  TEXT         NOT NULL,
    "unitType"      TEXT         NOT NULL,
    "rateMicroUsd"  BIGINT       NOT NULL,
    "unitQuantity"  BIGINT       NOT NULL,
    "effectiveFrom" TIMESTAMPTZ(6) NOT NULL,
    "effectiveTo"   TIMESTAMPTZ(6),
    "provenance"    TEXT         NOT NULL,
    "sourceUrl"     TEXT,
    "sourceReadAt"  TIMESTAMPTZ(6),
    "note"          TEXT,
    "createdAt"     TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "price_rates_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "price_rates_provider_modelName_unitType_deliveryMode_effect_idx"
    ON "price_rates" ("provider", "modelName", "unitType", "deliveryMode", "effectiveFrom");

-- ── Closed vocabularies. A new value is a migration, and that refusal is the
--    feature: an undeclared provider/unit/mode would price something by accident.
ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_provider_vocabulary"
    CHECK ("provider" IN ('anthropic', 'deepgram', 'openai'));

ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_delivery_mode_vocabulary"
    CHECK ("deliveryMode" IN ('pre_recorded', 'streaming', 'not_applicable'));

ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_provenance_vocabulary"
    CHECK ("provenance" IN ('published', 'invoice', 'console'));

-- ── SPEC §4.5, enforced rather than described.
ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_published_needs_source"
    CHECK ("provenance" <> 'published'
           OR ("sourceUrl" IS NOT NULL AND "sourceReadAt" IS NOT NULL));

-- ── The rate is an exact rational and its denominator is not free-form.
ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_unit_quantity_matches_type"
    CHECK (
      ("unitType" IN ('tokens_input', 'tokens_output', 'cache_write_5m',
                      'cache_write_1h', 'cache_read') AND "unitQuantity" = 1000000)
      OR ("unitType" = 'audio_minutes' AND "unitQuantity" = 1)
    );

ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_rate_non_negative"
    CHECK ("rateMicroUsd" >= 0);

-- ── A period that ends before it begins is not a period.
ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_period_ordered"
    CHECK ("effectiveTo" IS NULL OR "effectiveTo" > "effectiveFrom");

-- ── THE ONE THAT MAKES VERSIONING A PROPERTY AND NOT A HABIT.
--    Two rows sharing a key may not have overlapping effective periods, so
--    "which rate applied at instant T" has exactly one answer, always.
--    `'[)'` — start inclusive, end exclusive — so a change at midnight is a
--    clean handover with no instant belonging to both rows and none to neither.
ALTER TABLE "price_rates" ADD CONSTRAINT "price_rates_no_overlap"
    EXCLUDE USING gist (
      "provider"     WITH =,
      "modelName"    WITH =,
      "unitType"     WITH =,
      "deliveryMode" WITH =,
      tstzrange("effectiveFrom", "effectiveTo", '[)') WITH &&
    );

-- ============================================================================
-- THE SEED — DISCOVERY §D, read 2026-08-04 from the vendors' own pages.
--
-- Micro-dollars are exact: $5.00 / MTok  → 5000000 µ$ per 1000000 tokens.
--                          $0.10 / MTok  →  100000 µ$ per 1000000 tokens.
--                          $0.0077 / min →    7700 µ$ per 1 audio minute.
-- Every figure below is dollars × 1 000 000, and is checkable by eye against
-- the tables in DISCOVERY §D.1–D.3.
-- ============================================================================

INSERT INTO "price_rates"
  ("id", "provider", "modelName", "deliveryMode", "unitType",
   "rateMicroUsd", "unitQuantity", "effectiveFrom", "effectiveTo",
   "provenance", "sourceUrl", "sourceReadAt", "note")
VALUES
  -- ── ANTHROPIC ────────────────────────────────────────────────────────────
  -- Five unit types per model-period. The two cache-WRITE classes are separate
  -- rows because the vendor charges 1.25× and 2×, and the code collapses them
  -- into one 1.25× (`pricing.ts:claudeCostCents`) — correct today only because
  -- the single caching call site uses ephemeral 5m (DISCOVERY §C.8). One config
  -- change from a 60% under-charge; the table refuses to inherit that.

  -- Claude Opus 5 — $5 / $25, cache 6.25 / 10 / 0.50
  ('b3seed_ant_op5_in',   'anthropic', 'claude-opus-5', 'not_applicable', 'tokens_input',    5000000,  1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op5_out',  'anthropic', 'claude-opus-5', 'not_applicable', 'tokens_output',  25000000,  1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op5_cw5',  'anthropic', 'claude-opus-5', 'not_applicable', 'cache_write_5m',  6250000,  1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op5_cw1h', 'anthropic', 'claude-opus-5', 'not_applicable', 'cache_write_1h', 10000000,  1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op5_cr',   'anthropic', 'claude-opus-5', 'not_applicable', 'cache_read',       500000,  1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),

  -- Claude Opus 4.8 — the CURRENT DEFAULT for L4 SOAP draft, L5 critique,
  -- L7c Rx drafting, chat edit, template parse (334 rows in prod today).
  ('b3seed_ant_op48_in',   'anthropic', 'claude-opus-4-8', 'not_applicable', 'tokens_input',    5000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op48_out',  'anthropic', 'claude-opus-4-8', 'not_applicable', 'tokens_output',  25000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op48_cw5',  'anthropic', 'claude-opus-4-8', 'not_applicable', 'cache_write_5m',  6250000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op48_cw1h', 'anthropic', 'claude-opus-4-8', 'not_applicable', 'cache_write_1h', 10000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op48_cr',   'anthropic', 'claude-opus-4-8', 'not_applicable', 'cache_read',       500000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),

  -- Claude Opus 4.7 — no live call site today; `pricing.ts:119` still dispatches
  -- it, so the meter would record the name verbatim if anything repointed.
  ('b3seed_ant_op47_in',   'anthropic', 'claude-opus-4-7', 'not_applicable', 'tokens_input',    5000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op47_out',  'anthropic', 'claude-opus-4-7', 'not_applicable', 'tokens_output',  25000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op47_cw5',  'anthropic', 'claude-opus-4-7', 'not_applicable', 'cache_write_5m',  6250000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op47_cw1h', 'anthropic', 'claude-opus-4-7', 'not_applicable', 'cache_write_1h', 10000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_op47_cr',   'anthropic', 'claude-opus-4-7', 'not_applicable', 'cache_read',       500000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),

  -- ⚠️ Claude Sonnet 5 — TWO PERIODS, AND THIS PAIR IS WHY THE TABLE IS
  --    VERSIONED BY DATE RATHER THAN BY MODEL NAME. The vendor's introductory
  --    rate ends 2026-08-31 and the standard rate begins 2026-09-01. Same model
  --    id, two prices, and a call made in August must still price at the August
  --    rate in October. That is B3's gate, and it is demonstrated here on a real
  --    published change rather than an invented one.
  --    The vendor published DATES, not instants; the boundary is taken at
  --    00:00:00Z and the assumption is recorded on the rows.
  ('b3seed_ant_so5a_in',   'anthropic', 'claude-sonnet-5', 'not_applicable', 'tokens_input',   2000000, 1000000, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z', 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Introductory rate, vendor-stated as running through 2026-08-31. Boundary taken at 00:00:00Z; the vendor published a date, not an instant.'),
  ('b3seed_ant_so5a_out',  'anthropic', 'claude-sonnet-5', 'not_applicable', 'tokens_output', 10000000, 1000000, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z', 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Introductory rate through 2026-08-31; boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5a_cw5',  'anthropic', 'claude-sonnet-5', 'not_applicable', 'cache_write_5m', 2500000, 1000000, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z', 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Introductory rate through 2026-08-31; boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5a_cw1h', 'anthropic', 'claude-sonnet-5', 'not_applicable', 'cache_write_1h', 4000000, 1000000, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z', 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Introductory rate through 2026-08-31; boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5a_cr',   'anthropic', 'claude-sonnet-5', 'not_applicable', 'cache_read',      200000, 1000000, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z', 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Introductory rate through 2026-08-31; boundary taken at 00:00:00Z.'),

  ('b3seed_ant_so5b_in',   'anthropic', 'claude-sonnet-5', 'not_applicable', 'tokens_input',   3000000, 1000000, '2026-09-01T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Standard rate, vendor-stated as beginning 2026-09-01. Boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5b_out',  'anthropic', 'claude-sonnet-5', 'not_applicable', 'tokens_output', 15000000, 1000000, '2026-09-01T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Standard rate from 2026-09-01; boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5b_cw5',  'anthropic', 'claude-sonnet-5', 'not_applicable', 'cache_write_5m', 3750000, 1000000, '2026-09-01T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Standard rate from 2026-09-01; boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5b_cw1h', 'anthropic', 'claude-sonnet-5', 'not_applicable', 'cache_write_1h', 6000000, 1000000, '2026-09-01T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Standard rate from 2026-09-01; boundary taken at 00:00:00Z.'),
  ('b3seed_ant_so5b_cr',   'anthropic', 'claude-sonnet-5', 'not_applicable', 'cache_read',      300000, 1000000, '2026-09-01T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Standard rate from 2026-09-01; boundary taken at 00:00:00Z.'),

  -- Claude Sonnet 4.6 — the CURRENT DEFAULT for L3 entities, L4b anchor verify,
  -- L6 polish, L6b fidelity gate (769 rows in prod today, the busiest model).
  ('b3seed_ant_so46_in',   'anthropic', 'claude-sonnet-4-6', 'not_applicable', 'tokens_input',   3000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_so46_out',  'anthropic', 'claude-sonnet-4-6', 'not_applicable', 'tokens_output', 15000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_so46_cw5',  'anthropic', 'claude-sonnet-4-6', 'not_applicable', 'cache_write_5m', 3750000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_so46_cw1h', 'anthropic', 'claude-sonnet-4-6', 'not_applicable', 'cache_write_1h', 6000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_so46_cr',   'anthropic', 'claude-sonnet-4-6', 'not_applicable', 'cache_read',      300000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),

  -- Claude Haiku 4.5, and its dated alias. `pricing.ts:126-127` dispatches BOTH
  -- names, so the meter can record either verbatim; two names, two rows, same
  -- rate. A rate keyed on a name the meter never emits is a rate nothing finds.
  ('b3seed_ant_ha45_in',   'anthropic', 'claude-haiku-4-5', 'not_applicable', 'tokens_input',   1000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_ha45_out',  'anthropic', 'claude-haiku-4-5', 'not_applicable', 'tokens_output',  5000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_ha45_cw5',  'anthropic', 'claude-haiku-4-5', 'not_applicable', 'cache_write_5m', 1250000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_ha45_cw1h', 'anthropic', 'claude-haiku-4-5', 'not_applicable', 'cache_write_1h', 2000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),
  ('b3seed_ant_ha45_cr',   'anthropic', 'claude-haiku-4-5', 'not_applicable', 'cache_read',      100000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', NULL),

  ('b3seed_ant_ha45d_in',   'anthropic', 'claude-haiku-4-5-20251001', 'not_applicable', 'tokens_input',   1000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Dated alias of claude-haiku-4-5; pricing.ts dispatches both names.'),
  ('b3seed_ant_ha45d_out',  'anthropic', 'claude-haiku-4-5-20251001', 'not_applicable', 'tokens_output',  5000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Dated alias of claude-haiku-4-5.'),
  ('b3seed_ant_ha45d_cw5',  'anthropic', 'claude-haiku-4-5-20251001', 'not_applicable', 'cache_write_5m', 1250000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Dated alias of claude-haiku-4-5.'),
  ('b3seed_ant_ha45d_cw1h', 'anthropic', 'claude-haiku-4-5-20251001', 'not_applicable', 'cache_write_1h', 2000000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Dated alias of claude-haiku-4-5.'),
  ('b3seed_ant_ha45d_cr',   'anthropic', 'claude-haiku-4-5-20251001', 'not_applicable', 'cache_read',      100000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://platform.claude.com/docs/en/docs/about-claude/pricing', '2026-08-04T00:00:00Z', 'Dated alias of claude-haiku-4-5.'),

  -- ── DEEPGRAM — 2 of the 3 rates B3 owes. The third is PARKED, above. ──────
  -- `nova-3` general is what interpreter-mode visits actually send
  -- (`01-transcribe.ts:158`, `01b-transcribe-dictation.ts:130`) because
  -- nova-3-medical is English-only. Both of those are PRE-RECORDED calls
  -- through the batch endpoint, whatever `api-usage.ts` labels them.
  --
  -- ⚠️ THE TIER IS AN ASSUMPTION AND IT IS RECORDED AS ONE. These are the
  --    published PAY-AS-YOU-GO figures. Deepgram also publishes Growth-tier
  --    rates ($0.0065 / $0.0042) and DISCOVERY §D.2 does not establish which
  --    tier this account is on. PAYG is the higher number, so a wrong guess
  --    here OVER-states cost — and with `charge = cost × 3 / 2` that would
  --    over-bill, which is the direction that matters. The vendor request now
  --    asks for the tier by name; it is the same conversation that unblocks
  --    nova-3-medical.
  ('b3seed_dg_n3_pre',    'deepgram', 'nova-3', 'pre_recorded', 'audio_minutes', 7700, 1, '2026-08-04T00:00:00Z', NULL, 'published', 'https://deepgram.com/pricing', '2026-08-04T00:00:00Z', 'Nova-3 Monolingual, pay-as-you-go, pre-recorded. TIER ASSUMED PAYG — unconfirmed for this account; see docs/foundation/B3-deepgram-rate-request.md.'),
  ('b3seed_dg_n3_stream', 'deepgram', 'nova-3', 'streaming',    'audio_minutes', 4800, 1, '2026-08-04T00:00:00Z', NULL, 'published', 'https://deepgram.com/pricing', '2026-08-04T00:00:00Z', 'Nova-3 Monolingual, pay-as-you-go, streaming. NO STREAMING CALL SITE EXISTS TODAY — every Deepgram call on this stack is pre-recorded; api-usage.ts labels them transcribe_realtime, which is a literal, not an observation (DISCOVERY §C.7). Seeded because B3 owes the rate, not because the path runs. TIER ASSUMED PAYG.'),

  -- ── OPENAI ───────────────────────────────────────────────────────────────
  -- whisper-1 is the cross-provider transcription fallback (`whisper-batch.ts:32`),
  -- reached only when the operator has enabled it post-BAA.
  ('b3seed_oa_whisper', 'openai', 'whisper-1', 'pre_recorded', 'audio_minutes', 6000, 1, '2026-08-04T00:00:00Z', NULL, 'published', 'https://developers.openai.com/api/docs/pricing', '2026-08-04T00:00:00Z', NULL),

  -- ⚠️ text-embedding-3-small — $0.02 / 1M tokens. THIS ROW IS A CORRECTION,
  --    and it is the fourth one B3 carries. Two in-code surfaces disagree by
  --    6.5×: `pricing.ts:170` has 2 cents/M (= $0.02/M, correct) and
  --    `api-usage.ts:66` has `openai_embedding: 0.13` (= $0.13/M, unsourced and
  --    matching no figure OpenAI publishes). The durable billing source — which
  --    ruling 78(b) makes `api_usage_events` — is the one holding the wrong,
  --    higher number. Impact today is zero only because the embed usage builder
  --    (`api-usage.ts:365`) HAS NO CALLER, so no embed row has ever reached the
  --    meter; `ai_calls` holds 37. Same shape as the Deepgram 3.4×: harmless
  --    until the day it is wired, which is B4.
  ('b3seed_oa_embed_small', 'openai', 'text-embedding-3-small', 'not_applicable', 'tokens_input', 20000, 1000000, '2026-08-04T00:00:00Z', NULL, 'published', 'https://developers.openai.com/api/docs/pricing', '2026-08-04T00:00:00Z', 'CORRECTION: api-usage.ts PRICING.openai_embedding says $0.13/M, 6.5x this published figure and unsourced. pricing.ts agrees with this row. Neither in-code constant is patched by B3 (SPEC 4.5); the table supersedes them in B4/B6.');

-- ── RESEND IS ABSENT, AND THAT IS A RULING, NOT AN OMISSION. ────────────────
--    GATE 0.5 (SPEC §4.5): Resend is a SUBSCRIPTION, not a per-run meter, so it
--    cannot be charged as cost × 3 / 2 per event. Its 219 `api_usage_events`
--    rows become a fixed cost line in B9's monthly reconciliation. A price row
--    for it would invite exactly the per-event charge the ruling forbids.

-- ============================================================================
-- THE SEED PROVES ITS OWN APPLICATION.
--
-- AGENTS.md: a scripted edit states the number of rows it expects and asserts
-- the number it actually wrote; a mismatch ABORTS. A migration that half-applies
-- and reports success is the failure mode — here it would be a price table
-- silently missing a model, which reads identically to a model nobody uses.
-- ============================================================================
DO $$
DECLARE
  total    INT;
  anthro   INT;
  deepgram INT;
  openai   INT;
  bad_prov INT;
  medical  INT;
BEGIN
  SELECT count(*) INTO total    FROM "price_rates";
  SELECT count(*) INTO anthro   FROM "price_rates" WHERE "provider" = 'anthropic';
  SELECT count(*) INTO deepgram FROM "price_rates" WHERE "provider" = 'deepgram';
  SELECT count(*) INTO openai   FROM "price_rates" WHERE "provider" = 'openai';

  -- 8 Anthropic model-periods x 5 unit types = 40; 2 Deepgram; 2 OpenAI.
  IF total <> 44 OR anthro <> 40 OR deepgram <> 2 OR openai <> 2 THEN
    RAISE EXCEPTION
      'B3 seed did not apply as declared: total=% (want 44), anthropic=% (want 40), deepgram=% (want 2), openai=% (want 2)',
      total, anthro, deepgram, openai;
  END IF;

  -- Every seeded row is `published` and therefore must carry url + read-date.
  -- The CHECK already refuses the row; this asserts the SEED chose correctly
  -- rather than relying on the constraint to have caught a mistake silently.
  SELECT count(*) INTO bad_prov FROM "price_rates"
    WHERE "provenance" <> 'published'
       OR "sourceUrl" IS NULL OR "sourceReadAt" IS NULL;
  IF bad_prov <> 0 THEN
    RAISE EXCEPTION 'B3 seed: % row(s) lack a published source', bad_prov;
  END IF;

  -- ⚠️ THE ABSENCE OF nova-3-medical IS ASSERTED, NOT ASSUMED. If a future edit
  -- seeds it from the undated announcement post, this migration is not the place
  -- it should land, and a later reader must not find it here without a ruling.
  SELECT count(*) INTO medical FROM "price_rates" WHERE "modelName" = 'nova-3-medical';
  IF medical <> 0 THEN
    RAISE EXCEPTION
      'B3 seed: nova-3-medical must NOT be seeded here — SPEC 4.5 disqualifies its undated source. Found % row(s).',
      medical;
  END IF;
END $$;
