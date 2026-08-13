# Delta declarations — one file per deploy, written BEFORE it runs

`scripts/deploy-prod.sh` **refuses to run** without a declaration for the commit
being deployed:

    docs/foundation/deploys/<UTC-date>-<short-sha>.md

## Why the file, and why the order

⚠️ **The file is not the point. The ORDER is.**

A post-deploy check written afterwards is unfalsifiable — every number has a
story available to it, and a migration supplies a ready-made excuse for *any*
movement ("the migration touched that table"). A declaration that exists **before
the evidence** has exactly one correct answer, fixed while the outcome was still
unknown.

The deploy prints the declaration into its transcript at step 0 and **re-reads
the same file** at step 8, so the thing being judged against cannot be quietly
rewritten to fit what happened.

## Two gates, two strictnesses

| path | script | the declaration must be |
|---|---|---|
| deploy (reversible — a rollback exists) | `deploy-prod.sh` | **present**; provenance printed, uncommitted warns loudly |
| ruled mutation (irreversible) | `run-ruled-mutation.sh` | **tracked, unmodified and COMMITTED** |

⚠️ **The asymmetry is deliberate**: strictness proportional to reversibility. And
the stricter half exists because *"the file exists"* never proved *"the file
existed first"* — see the B7 step 3c reference case in AGENTS.md §"A DEPLOY
DECLARES ITS EXPECTED DELTA BEFORE IT RUNS".

## What it must contain

- **BASELINE** — captured now, before anything changes.
- **MUST change** — and nothing else may.
- **MUST NOT change** — ⚠️ **the clinical counts are never omitted.** A deploy
  that moves a visit, patient or signature count has done something nobody asked
  for, and the only way to know is to have written the numbers down while they
  were still true.
- **What would make this check FAIL** — say it, so the check can.

## Known-good example

`docs/foundation/RELAY.md`'s T7 row records a declaration that caught its own
brief's error before the deploy ran: the war room said "84 rows backfilled", the
measurement said 84 gain the column and **82** receive a value. Stating it first
is what made the correction possible; afterwards, "84" would have had an
explanation.
