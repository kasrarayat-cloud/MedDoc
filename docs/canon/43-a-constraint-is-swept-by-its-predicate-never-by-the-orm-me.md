> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **91 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A CONSTRAINT IS SWEPT BY ITS PREDICATE, NEVER BY THE ORM METHOD

**Standing rule for every CHECK, NOT NULL, unique or FK you add.** The universe
to sweep is *"every write that can produce the forbidden state"* — which is a
statement about BEHAVIOUR. `create` / `upsert` / `update` are API verbs, and the
set of verbs is the wrong universe. This is the coverage-vs-criteria class
arriving at the write layer: the sweep is flawless over a set that does not
contain the offending write.

> **Write the constraint's predicate down in words, then find every site that
> can make it false.** If you catch yourself listing method names, you have
> already substituted a proxy for the question.

⚠️ **REFERENCE CASE — T6's `users_active_member_has_practice_role`, 2026-08-07.**
The predicate is *"an ACTIVE user WITH a practice HAS a role"*. Two distinct
errors, both mine, in one sweep:

**(a) The verb filter — 9 sites vs 24.** I swept
`user.(create|upsert|createMany)` and found 9. There are **24** user write
sites; the other 15 are `update`. An `update` setting `isActive: true` on a row
with a practice and no role violates the CHECK just as a `create` does —
**reactivation is a write that can produce the forbidden state**, and no `create`
sweep will ever see it. It surfaced a real latent bug: a user deactivated BEFORE
the backfill carries a practice with a NULL role, because the backfill
deliberately skips deactivated rows, so reactivating them fails with an error
naming the CHECK and not the cause.

**(b) The inventory was taken ONE LAYER ABOVE THE FIELDS.** My scan extracted the
balanced argument of each `prisma.user.upsert(...)` and read its keys.
`seed-qa-user.ts` passes a payload built by an EXTRACTED FUNCTION, so the call
site holds a *variable* — the scan reported `practiceId=False` and I believed it.
CI failed on that exact seed. This is the costume already named in the write-path
section above, worn again: **the thing lived one layer down.**

    A sweep over call sites cannot see fields that are assembled elsewhere.
    Sweep the FIELD (`practiceId:` in any object that also carries user-shaped
    keys), not the CALL — or read every payload builder by name.

**The corollary rule, from the fix:** *no-downgrade applies to reactivation too.*
Restore `OWNER` **only where the row has a practice and no role** — never
unconditionally, which would overwrite a real CLINICIAN or TECH assignment with
an owner's rights the moment somebody was un-suspended.

