# JUDGEMENT — ruling #226, the archive of six test practices

**Act executed 2026-09-07T08:36:52Z** through
`scripts/run-ruled-mutation.sh` under
`docs/deploy-declarations/20260907-r226-archive-six-test-practices.md`.

    declaration committed : 071b80ab  at 2026-09-07T08:35:42+00:00
    act starting at       :           2026-09-07T08:36:52Z   ← AFTER the commit

**The bracket holds.** The declaration's commit provably precedes the rows by
70 seconds, which is the distinction B7's backfill lost by one minute
fifty-seven seconds in the other direction.

## THE VERDICT — 9 of 9

⚠️ **RE-DERIVED INDEPENDENTLY OF THE SCRIPT'S OWN POST-VERIFY**, per #232: *an
act that reports its own success has not been judged.* The script's
`DO $post$` block passed and rolled nothing back; these are separate queries run
afterwards against the committed state.

| # | row | declared | measured |
|---|---|---|---|
| C1 | six practices flagged | 6 of 6 | **6 of 6** |
| C2 | users still divergent | 0 | **0** |
| C3 | five `deactivatedAt` = their own audit witness | 5 | **5** |
| C4 | five `deactivatedBy` = `r226-ruling-2026-09-07` | 5 | **5** |
| N1 | **clinical counts** — visits / signed | 58 / 40 | **58 / 40** |
| N2 | users / practices | 198 / 199 | **198 / 199** |
| N3 | `updatedAt` witness intact | 5 | **5** |
| N6 | practices archived OUTSIDE the six | 0 | **0** |
| N7 | practices with a live member and no able owner | 0 | **0** |

## ⚠️ ONE ROW READ WRONG FIRST, AND THE PROBE WAS THE DEFECT

C3 initially measured **17** against a declared **5**. The query was unscoped —
it counted *every* user whose `deactivatedAt` equals their `USER_DEACTIVATED`
audit timestamp, and production holds **17** deactivated users. Scoped to the
five the act touched: **5 of 5**, each equal to its witness at exactly
`2026-08-08 20:07:02.578745+00`.

**The other 12 all carry `gate0-ruling-2026-08-05` and were untouched** — which
is itself N6's sibling check, arrived at by accident and worth keeping.

*A number that does not match its declaration is a finding until it is
explained, and the explanation here is that the instrument was wrong. That is
the third probe of this session to answer confidently about the wrong universe.*

## WHAT WAS WRITTEN

**Six practices** — `isActive = false`, a **MARKER**: nothing reads
`practices.isActive` (the only `isActive` reads in the tree are on the USER row,
`auth.ts:69`). It disables nothing and is not claimed to.

**Five users** — `deactivatedAt` set to the **recovered** instant
`2026-08-08 20:07:02.578745+00`, re-derived from the audit trail **at run time**
with a refusal arm if the witnesses disagreed; `deactivatedBy` set to
`r226-ruling-2026-09-07`, the ruling identifier, matching the
`gate0-ruling-2026-08-05` practice on the other two users of this population.

⚠️ **`updatedAt` was never named in the UPDATE**, and N3 proves it survived. It
is `@updatedAt`; a Prisma write would have bumped it and destroyed the
corroborating witness to the very timestamp being recorded.

## THE RECORD

Per #230, **no new enum value was spent.** The record of this act is:

1. **the declaration commit** `071b80ab`, tracked and naming all six by id and
   classification;
2. **the five pre-existing `USER_DEACTIVATED` audit rows** from the 2026-08-08
   containment, which the reconciliation makes the user rows agree with;
3. **this judgement.**

A real `PRACTICE_ARCHIVED` action arrives with practice-lifecycle work in the
ADMIN arc, with its own migration. **These six get their rows then.**

## RESTORE

Unchanged and still available — no row was deleted, no enum value added, no
column dropped. The exact SQL is in the declaration's RESTORE section, and it was
rehearsed on an isolated clone: it returns the database to precisely the pre-act
state.
