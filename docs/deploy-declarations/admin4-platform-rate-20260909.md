# §2.5 DECLARATION — ADMIN-4, the platform margin becomes a row

**Written and committed BEFORE the act.** Change: `feat/admin4-platform-rate`.
One migration, `20260909060000_admin4_platform_rate`.

## WHAT MUST CHANGE

| # | quantity | before | after |
|---|---|---|---|
| 1 | `platform_rates` table | does not exist | exists, **0 rows** |
| 2 | `platform_rates` CHECK constraints | — | **5** (`margin_bounds`, `previous_pair`, `previous_bounds`, `actor_present`, `forward_only`) |
| 2b | `platform_rates` TRIGGERS | — | **4** (`stamp_created_before_insert`, `no_update`, `no_delete`, `no_truncate`) |
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

## ⚠️ AMENDED AGAIN AFTER ROUND 2 — and the pattern is the finding

Round 2 aimed three lenses at round 1's *repairs* and broke four of them. **Each
round-1 fix had closed the INSTANCE it was shown and left the CLASS:**

| round 1 fixed | round 2 broke it by |
|---|---|
| `marginStamp()` extracted so the stamp is assertable | substituting its **argument** — the arm greps for the token |
| the anchor moved below the `unitsSource` skip | hoisting it above the **sibling** skip one line below |
| `forward_only` CHECK | supplying **`createdAt`** too — Prisma generates it optional |
| bounds enforced at the point of use | importing `chargeMicroUsd` from the **barrel**, which withheld the guard |

**Row 2b is new: three triggers.** `createdAt` is now server-stamped
(`NEW."createdAt" := now()`), and the table is append-only — because the CHECK
compared two columns *the writer supplies*, and an `UPDATE` re-priced
retroactively without touching either.

⚠️ **And the append-only trigger carves out exactly one update — the
`ON DELETE SET NULL` detach of `changedByUserId`.** Without it, the rate history
would hold user deletion hostage. `ledger_entries` documents that same hole one
table over and solves it the same way; `changedByLabel` is why the actor
survives the detach.

**Rows 4–10 are unaffected.** Still additive, still an empty table.

## ⚠️ AMENDED A THIRD TIME — round 3, and one lens used a real database

Round 3 ran the migration byte-for-byte on a throwaway `postgres:16-alpine` and
attacked it. DELETE, UPDATE, a backdated INSERT, `ON CONFLICT DO UPDATE` and
`COPY` were each refused by name. **`TRUNCATE "platform_rates";` emptied the
table, 2 rows to 0, silently** — row-level triggers do not see it.

⚠️ **The prior art this migration says it copied has that arm, and its comment
is the warning I walked past:** *"TRUNCATE FIRES NEITHER OF THE ABOVE … it is
the arm most likely to be left out."* It was. **Row 2b goes 3 → 4.**

Also from round 3, all fixed:

- the migration now **verifies itself** (`DO $verify$`, 4 triggers / 3 CHECKs).
  `prisma migrate dev` cannot see triggers and would regenerate this file
  without them — the exact class this diff quoted *twice* and did not guard.
- `createdAt` is stamped with **`clock_timestamp()`**, not `now()`:
  transaction-start time gave a retroactive window equal to the writing
  transaction's duration (**measured: 3.011s**).
- `chargeMicroUsd` now **refuses** an out-of-bounds margin itself. Round 2
  exported the guard beside it, which made it discoverable and left the domain
  unchanged — `chargeMicroUsd(1000n, {1,2})` still returned 500n from the public
  barrel. **A precondition somebody must remember to call is documentation with
  a type, not enforcement.**

Rows 4–10 unaffected.

## ⚠️ AMENDED A FOURTH TIME — round 4, and the first finding was my own regression

Round 4 applied the migration byte-for-byte to a real PG 16.13 and attacked it.

⚠️ **Round 3's `clock_timestamp()` fix had stranded the writer completely.**
`effectiveFrom = now()` was **refused by nine microseconds** — `now()` is
transaction-start, the stamp is statement-time. Every honest spelling failed;
only a *guessed* future offset landed (+1 ms refused, +10 ms accepted), and
Prisma sends a client-computed `new Date()` which is earlier still. **The writer
#178 calls for could not have set a rate at all**, and the refusal would have
read like an attack being blocked. Fail-closed is the rule; **stranding is not**.

`effectiveFrom` is now **nullable on the way in**, meaning *immediately*, filled
by the trigger from the server's own clock. Both properties at once: no
retroactive window, and one spelling that cannot lose the race.

Three more, all verified on the same database:

- the self-verify counted by **`relname`**, so a decoy `archive.platform_rates`
  made it report 4 triggers while `public` had 3 — **certifying a table that had
  lost its TRUNCATE arm**. Now `regclass`, matching the prior art verbatim.
- `changedByLabel NOT NULL` accepted **`''`** — a price change with no actor.
  New CHECK.
- the **previous** pair accepted `0/0` and `-7/-1`. New CHECK, same bounds as the
  current value. **Row 2 goes 3 → 5.**

**Measured after the fixes, on the real database:** immediate ✅ · backdated
refused · TRUNCATE refused · blank actor refused · `0/0` previous refused ·
out-of-bounds refused · UPDATE refused · a legitimate future row lands.

---

## ⚠️ AMENDED A FIFTH TIME — round 5, and ONE ROW HERE IS AN OPERATIONAL PRECONDITION

Round 5's refutation pass upheld ten findings. Seven were fixed (see the commits
on `feat/admin4-platform-rate`); three were adjudicated as the ruled property and
are recorded rather than changed. **One of them adds a precondition to the flag
flip and it belongs in this document, because this is what the person flipping
the flag reads.**

### THE PRECONDITION

> **Write the first `platform_rates` row BEFORE `BILLING_ENFORCED` is turned on.**

`platform_rates_forward_only` — a guard ROUND 1 of this branch added deliberately,
because a backdated row re-pricing every uncharged visit was the defect that pass
found — means **a rate can never reach usage that predates it.** Every backdating
route was re-measured on PG 16.15 and each is refused BY NAME:
`INSERT` with a past `effectiveFrom`, `INSERT` with `createdAt` backdated too,
`UPDATE`, and `DELETE`-then-reinsert.

So usage metered between the flag going on and the first rate being written can
never be charged. That is ruling #178 working (*"forward only, past bills are
never rewritten"*, and *"a missing multiplier REFUSES, never bills 0"*), not a
gap — **and the window is empty under correct sequencing**, because nothing gates
a `platform_rates` write on the flag.

⚠️ **What is NOT lost, so the trade is judged on what it actually costs:**
`api_usage_events` rows are never updated or deleted by anything in the tree, so
any uncharged visit stays permanently enumerable as *"a usage event with no
ledger row"* — the recovery `commitVisitCharge` already names and B9 exists to
do — and the exact micro-dollar figure is recomputable from those immutable rows
forever. The documented offset is an `adjustment` ledger row.

### THE OTHER TWO ADJUDICATIONS, recorded so they are not re-raised

- **The margin is read ONCE, at the LATEST priced instant, and applies to the
  whole charge.** Measured: a two-instant visit spanning a rate change bills the
  whole cost at the later rate (1000 µ$ -> 5000 at 5/1, not 800×3/2 + 200×5/1 =
  2200). That is #178's own anchor — *"the multiplier in effect at BILLING
  TIME"* — and reading at the last USAGE instant is strictly tighter than
  billing time. Per-component anchoring is prescribed nowhere and is
  unrepresentable in the ruled stamp, which carries ONE multiplier per ledger
  line. **Pinned by a test; changing it is a money-policy call for the owner.**
- **A rate is EFFECTIVE at its INSERT statement and VISIBLE at COMMIT**, so
  between those two instants it is already in the past and unreadable. Measured:
  a 5s transaction produced two different answers to one fixed-instant query.
  **No DDL closes it** — commit time is unobtainable, `now()` is worse, and a
  guessed future offset is what round 4 rejected for stranding the writer. Any
  closure is reader-side TypeScript. Recorded in the migration and the schema;
  the schema's claim that `effectiveFrom` *"can never be in the past"* was FALSE
  and is corrected.

### ROW 2 IS UNCHANGED AT 5 CHECKS AND 4 TRIGGERS

Round 5 changed the CONTENT of two CHECKs (`bigint` cross-multiply) and one CHECK
(the actor's trim set), and extended the existing BEFORE INSERT trigger to derive
`previous*` under an advisory lock. **No constraint or trigger was added or
removed**, so the migration's own self-verify block still expects 4 and 5, and the
declared counts in this document still hold.
