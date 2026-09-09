# §2.5 DECLARATION — ADMIN-4, the platform margin becomes a row

**Written and committed BEFORE the act.** Change: `feat/admin4-platform-rate`.
One migration, `20260909060000_admin4_platform_rate`.

## WHAT MUST CHANGE

| # | quantity | before | after |
|---|---|---|---|
| 1 | `platform_rates` table | does not exist | exists, **0 rows** |
| 2 | `platform_rates` CHECK constraints | — | **3** (`margin_bounds`, `previous_pair`, `forward_only`) |
| 3 | `platform_rates` FK to `users` | — | **1**, `ON DELETE SET NULL` |
| 4 | index on `effectiveFrom` | — | **1** |

## WHAT MUST **NOT** CHANGE — and these are the rows that matter

| # | quantity | expected |
|---|---|---|
| 5 | `ledger_entries` count | **unchanged** |
| 6 | `usage_events` count | **unchanged** |
| 7 | `transcribe_visits` count | **unchanged** |
| 8 | patients, signatures | **unchanged** |
| 9 | `price_rates` rows | **unchanged** — the VENDOR table is untouched |
| 10 | `BILLING_ENFORCED` in the prod compose | **still absent** (grep = 0) |

⚠️ **THE CLINICAL COUNTS ARE HERE BECAUSE A DEPLOY THAT MOVES ONE HAS DONE
SOMETHING NOBODY ASKED FOR**, and the only way to know is to have written them
down while they were still true.

## THE DELIBERATE ZERO — read this before judging row 1

**`platform_rates` is created EMPTY, and that is the design, not an omission.**

Seeding `3/2` would make the migration itself the thing that decided the rate,
with no actor and no note — the same defect one layer up, in a migration's
clothes. Ruling #178 forbids *"a rate nobody can change without a deploy, and —
worse — a rate with no audit row saying who changed it"*; a seeded row is
exactly that, with a timestamp.

## WHAT THIS CHANGES IN PRODUCTION BEHAVIOUR — stated plainly

**The charge path does not run.** `BILLING_ENFORCED` is absent from the
production compose (grep: 0 hits) and `commitVisitCharge` additionally calls
`assertProdDatabase()`. Nothing bills today and nothing bills after this.

⚠️ **THE FAILURE-COST OBSERVER DOES RUN, AND ITS OUTPUT CHANGES.**
`worker.ts:1658 → billing-failure.ts → priceUsageRows` is live and no flag
covers it — this was the nine-row recon's find, and it is the third consumer
neither #178 nor the row's own cell named. With `platform_rates` empty it will
now record:

    observed: 'unpriceable', reason: 'no_margin_rate'

where it previously recorded a `wouldChargeMicroUsd` computed at the compiled
3/2. **That is the honest reading and it is the point**: the platform has no
configured margin, so the observer says so instead of quoting a number nobody
set. It is an OBSERVATION path — it writes no ledger row and charges nothing.

## ROLLBACK

`git revert` the merge, then `DROP TABLE platform_rates`. No data is lost: the
table is empty by construction and nothing reads it except the pricing path,
which returns to the compiled constant with the revert.

## WHAT WOULD MAKE ME SAY THIS FAILED

- any of rows 5–8 moving
- `price_rates` losing or gaining a row (row 9)
- `BILLING_ENFORCED` appearing anywhere in the prod compose (row 10)
- a ledger row written with a `multiplier` that does not resolve to a
  `platform_rates.id`

## ⚠️ AMENDED AFTER THE ADVERSARIAL PASS — before the act, and this is why §2.5 is written first

Four lenses returned **26 findings**. Six were real defects in this change and
are fixed; the declaration is amended rather than re-written, so the correction
is visible:

- **row 2 was `2` CHECKs, now `3`.** `platform_rates_forward_only` was added:
  `effectiveFrom >= createdAt`. The pass showed that anchoring the READ to the
  usage instant does **not** make the rate forward-only — a backdated row is
  selected by `effectiveFrom <= at` like any other, so inserting
  `{effectiveFrom: last month, 5/1}` would re-price every uncharged visit since
  then, at a stamp that resolves cleanly. My comment claimed forward-only was
  achieved; it was policy. It is now a constraint.
- **a new NOT NULL column, `changedByLabel`.** The FK detaches on user deletion
  (the house rule for audit rows), which would have erased *who changed the
  price* — the half of #178 that is not about the rate.

**No row above 4 changes**, and rows 5–10 are unaffected: this remains an
additive migration over an empty table.

