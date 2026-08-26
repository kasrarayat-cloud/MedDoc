> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **68 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## SPLIT-FAMILY COVERAGE PINS **BOTH** DIRECTIONS

**Standing 2026-08-14.** When a fix adds the missing half of a pair, asserting
only the half you added lets a future edit remove the half that was already
there — **reproducing the original defect inverted**, and a one-sided test
cannot see it.

⚠️ **REFERENCE CASE — four split families, each with exactly one member
present** before the cohort that fixed them:

| already there | was missing | the pair |
|---|---|---|
| `K21.9` | `K21.00` | GERD without vs WITH esophagitis |
| `K58.0` | `K58.1` | IBS-D vs IBS-C |
| `K57.30` | `K57.32` | diverticulosis vs diverticulitis |
| `Z12.11` | `K63.5` | the screening ENCOUNTER vs the FINDING it screens for |

A clinician documenting the other half had the code silently dropped, with only
a fire-and-forget audit row to show for it.

The guard iterates the pairs and asserts **both** members, with the failure
message naming which side went — *"K21.9 (the side that was already there)"*.
Mutation-proved by deleting the side that was **already** present, which is
precisely the direction a new-side-only test is blind to.

