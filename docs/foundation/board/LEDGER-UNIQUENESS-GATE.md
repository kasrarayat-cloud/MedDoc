# FILED — A MAIN-SIDE LEDGER UNIQUENESS GATE

**Filed 2026-09-06 from the #188 double-claim. Not built mid-sequence.**

## THE ASK

One **base row per ruling number** on `main`. Amendments are legitimate and must
be distinguished from duplicates **by their suffix**, not by the number.

## ⚠️ THE FIXTURE — AND IT CORRECTED THE FINDING THAT PROMPTED IT

I reported five existing collisions: #106, #109, #115, #116, #131. **Adjudicated
against `main`, all five are AMENDMENTS.** There is exactly **one** real
collision in the ledger — **#188**.

| # | rows | verdict |
|---|---|---|
| 106 | base + **(g)** | amendment |
| 109 | base + **(a)** | amendment |
| 115 | base + **b** | amendment |
| 116 | base + **b** + **(c)-CORRECTED** | amendment ×2 |
| 131 | base + **(b)** + **(c)** | amendment ×2 |
| **188** | **T4's clipboard ruling** + **the migration-strict rule** | ⚠️ **COLLISION** — two different rulings, same number, same day, different lanes |

⚠️ **MY DETECTION WAS THE DEFECT, AND IT IS THE GATE'S FIRST REQUIREMENT.** I
extracted `#([0-9]+)` and counted duplicates — a pattern that **strips the very
suffix that distinguishes an amendment from a duplicate**. `#106(g)` and `#106`
both reduced to `106`, so every amendment in the ledger read as a collision.

> **A uniqueness check on a namespace with suffixes must key on the FULL
> identifier. Dropping the discriminator is not a simplification; it is the bug.**

That is the same family as *an identifier is queried in its FULL form,
everywhere* — an abbreviated key returning a confident wrong answer — and it
produced a **5× overstatement** in a finding I reported before measuring.

## WHAT THE GATE MUST DO

1. **Partition, don't count.** Every row sorts into `base` / `amendment` /
   `collision`, and the three must reconcile to the row total — a bucket that
   does not add up is where the finding lives.
2. **Key on the full identifier**, suffix included.
3. **A base row appearing twice with different TEXT is a collision**; the same
   number with a suffix is an amendment.
4. ⚠️ **ADJUDICATE THE SUFFIX FORMAT FIRST.** `main` currently carries `(g)`,
   `(a)`, `(b)`, `(c)`, `(c)-CORRECTED` **and bare `b`** — `#115 b` and `#116 b`
   have no parentheses. A gate written against `\([a-z]\)` alone would classify
   those two as collisions and red `main` on arrival. **Measure the population
   before choosing the pattern**, or the gate's first act is a false accusation.
5. **Run on `main`, not per branch.** #188 is the proof: both lanes claimed at
   record time *correctly*, against a file neither could see the other editing.
   The conflict exists only in the **union**, and each branch was green alone.

## WHY IT IS WORTH BUILDING

The #188 collision surfaced only because a **live citation started pointing at
the wrong ruling** — one of them the §2.5 declaration for a production migration
deploy. **The detector was luck.** A duplicate row is untidy; a citation
resolving to somebody else's ruling means a reader is confidently misinformed.
