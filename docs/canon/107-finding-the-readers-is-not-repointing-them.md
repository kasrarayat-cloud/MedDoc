# FINDING THE READERS IS NOT REPOINTING THEM

**Ratified 2026-09-04.** [Canon
60](60-a-census-proves-content-not-reachability.md) says every ledger split
ships with its reader sweep. This entry is the failure one step later: **the
sweep ran, it found the readers, and the split shipped with half of them still
pointing at the old address.**

> **A reader sweep has two acts — ENUMERATE and REPOINT — and finishing the
> first feels like finishing both.**

## THE REFERENCE CASE

Ruling #183 moved the CANON INDEX out of `AGENTS.md` into
`docs/canon/INDEX.md`. The sweep was performed properly and returned seven
readers, among them:

    apps/transcribe-md/src/lib/__tests__/gate-172-arm-hygiene.test.ts
    apps/transcribe-md/src/lib/__tests__/gate-agents-md-size.test.ts

`gate-172` was repointed. `gate-agents-md-size` was not — **although it was in
the list, on screen, in the same output**. Four of its arms then failed:
row→file, file→row, the duplicate-number check, and the count reconciliation.
Every one of them reported **zero rows**, because they were slicing a region of
`AGENTS.md` that no longer existed.

## ⚠️ AND THE FAILURE IS NOT RELIABLY LOUD

Here it was loud, and only because those arms carried non-vacuity floors
(`toBeGreaterThan(50)`). Without them the same arms would have found **nothing
to check and passed**:

| the arm | with a floor | without one |
|---|---|---|
| every row points at a file | 0 rows → **RED** | 0 rows, 0 bad → **GREEN** |
| every body is reachable | 0 indexed → every body orphaned → **RED** | — |
| the count reconciles | 0 ≠ 146 → **RED** | — |

So a split that leaves a reader behind can report *every entry is missing*, or
it can report *everything is fine* — and which one you get is decided by whether
somebody put a floor in months earlier.

## THE PRACTICE

1. **Enumerate** the readers — grep for the OLD address, not for your new one
   ([canon 30](30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md):
   search for the problem, not for your fix).
2. **Repoint each one, and tick it off the list.** The list is the driver, not
   the context ([canon 35](35-the-list-is-the-driver-not-the-context.md)).
3. **Re-run the enumeration afterwards** and require it to be empty. That is the
   step that distinguishes "I found them" from "I fixed them", and it is one
   command:

       grep -rln '<the old address>' . | grep -v node_modules   # must be empty
       # or: the survivors are pointers/prose that SHOULD still name it

4. **Move the split's own artifacts out of the scanned set.** `INDEX.md` landing
   in `docs/canon/` made the orphan check count the index as a body nothing
   points at — a self-inflicted finding produced by the move itself.
5. **Re-check every count the prose claims.** The header said 144 entries against
   146 actual rows. *Arithmetic that does not reconcile is a finding*, including
   when the arithmetic is your own.
