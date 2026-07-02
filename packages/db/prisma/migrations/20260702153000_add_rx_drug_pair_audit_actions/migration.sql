-- F-8 audit leg (2026-07-02) — deterministic drug-PAIR interaction floor.
-- ----------------------------------------------------------------------------
-- Add the two RX_DRUG_PAIR_* enum values to AuditAction. Emitted by worker
-- layer 07c when checkDrugInteractions() (packages/ai/src/data/
-- drug-interactions.ts) fires on the union of drafted prescriptions and the
-- current-med list: a curated severe pair (RX_DRUG_PAIR_INTERACTION) or an
-- interaction-adjusted dose-cap breach / unverifiable dose
-- (RX_DRUG_PAIR_DOSE_CAP). Metadata carries { ruleId, primaryDrug, otherDrug,
-- severity, doseMgPerDay? } — drug names + rule class only, never note or
-- transcript content (the PR-D RX_* metadata contract).
--
-- Also closes the PR-D deferred follow-up (07c comment): the complex-dosing
-- verify nudge finally gets its audit row.
--
-- Idempotent: ADD VALUE IF NOT EXISTS (PG 9.6+). Additive enum values —
-- non-blocking, safe on a live database. New values are NOT used inside this
-- migration (PG12 same-transaction restriction).
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'RX_DRUG_PAIR_INTERACTION';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'RX_DRUG_PAIR_DOSE_CAP';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY';
