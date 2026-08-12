# §2.5 DELTA DECLARATION — THE B7 STEP 3c PROMO-GRANT BACKFILL

**Written 2026-08-12T22:50Z, BEFORE the backfill runs.** This is not a deploy —
it is ruling #99's step 3, and the README in this directory applies word for
word: a check written afterwards is unfalsifiable, and this one has exactly one
correct answer, fixed while the outcome was still unknown.

⚠️ **THIS IS THE FIRST ITEM IN THE PROGRAMME WHOSE CENTRAL ACT CANNOT BE
REVERTED.** `ledger_entries` refuses DELETE and UPDATE by design. The rows this
writes are permanent; the only instrument afterwards is an `adjustment` row that
offsets the balance and then lives beside the grant forever.

**Authorization:** the owner's written authorization recorded verbatim in
`RELAY.md` and ruling **#99**, ratified by **#100**. Not a session's decision.

---

## PRECONDITIONS — all four met before this was written

| precondition | state |
|---|---|
| deploy debt cleared | ✔ `2f028788` deployed by session 01 |
| **step 3c code + migration live in production** | ✔ `a580afcd` deployed 22:44Z, declaration judged **11 of 11** |
| **`AuditAction.PROMO_GRANT_CREDITED` present in `pg_enum`** | ✔ `f` → **`true`**, measured post-deploy — GUARD 0's precondition |
| QA rehearsal with every guard proven to fire | ✔ session 01, three defects killed |

---

## BASELINE — measured against production 2026-08-12T22:47Z, post-deploy

| quantity | value |
|---|---|
| practices total | **197** |
| practices with an active member (**the population**) | **175** |
| `ledger_entries` | **0** |
| promo bucket sum | **0** micro-USD |
| paid bucket sum | **0** micro-USD |
| `audit_logs` rows action=`PROMO_GRANT_CREDITED` | **0** |
| visits · signed · patients | **25 · 17 · 16** |
| `BILLING_ENFORCED` (app / worker) | **unset / unset** |

Grant constant, from the ruled source and not from this text:
`PROMO_GRANT_MICRO_USD = 10_000_000n` (`packages/ai/src/billing-grant.ts:110`)
— **$10.00** exactly.

---

## WHAT **MUST** CHANGE

1. **`ledger_entries` 0 → 175.** One `grant` row per active-member practice.
2. **promo bucket sum 0 → 1_750_000_000 micro-USD** — exactly
   **175 × $10.00 = $1,750.00**. Stated as an exact integer, not a range.
3. **`audit_logs` `PROMO_GRANT_CREDITED` rows 0 → 175** — one actor record per
   grant, **read back from the table**, never counted from the calls made.

## WHAT **MUST NOT** CHANGE

4. **paid bucket sum stays 0.** No paid balance moves. Ever, under this item.
5. **Clinical counts stay `visits 25 · signed 17 · patients 16`.** Never omitted.
6. **practices stay 197 total / 175 active-member.**
7. **`BILLING_ENFORCED` stays unset.** This funds wallets; it bills nobody.
8. **No second grant for any practice** — at most one `grant:promo:practice:<id>`
   key in the whole table.

---

## THE POPULATION IS **175**, AND THAT NUMBER IS BINDING

`--expect=175` is passed on the command line and **GUARD 2 aborts** if the
population the script re-derives at execution time is anything else. The 175 was
measured twice by this session — 22:01:50Z and 22:47Z — and is **not** copied
from `RELAY.md`.

⚠️ **IF THE DRY RUN DERIVES ANY OTHER NUMBER, THAT IS THE FINDING**, the run
aborts, and this declaration is rewritten before anything is committed. A
population that moved between the deploy and the backfill means a signup landed
in the window — which is *legitimate* and still must not be absorbed silently
into a number nobody re-declared.

The 22 excluded practices are ruled, not overlooked: **16 have no members at all**
(structurally dead — no reactivation exists to fund) and **6 have only deactivated
members** (covered by the reactivation door when anyone returns).

---

## WHAT WOULD MAKE THIS **FAIL**

Any one of these is a FINDING, whatever story is available afterwards:

- `ledger_entries` ≠ **175**, or promo sum ≠ **1_750_000_000** micro-USD
- **any** movement in the paid bucket
- `audit_logs` `PROMO_GRANT_CREDITED` ≠ **175** *(this is the one that shipped
  broken on QA — the script reported 11 while writing 0)*
- **any** movement in visits / signed / patients
- more than one grant row for any practice
- the script exiting non-zero, hanging, or a guard firing
- `BILLING_ENFORCED` set anywhere

## ORDER OF EXECUTION

1. **DRY RUN** — `--target=prod --expect=175`, no `--commit`. Runs the real path
   inside a transaction and throws `ROLLBACK`; a dry run that took a different
   code path would prove nothing about the real one. Expect: population 175,
   0 funded, 175 to write, guards 3–7 pass, **verified 0 written**.
2. **COMMIT** — the same command plus `--commit`, only if step 1 matched this
   declaration exactly.
3. **VERIFY** — re-measure every row of the table above, from the database.
