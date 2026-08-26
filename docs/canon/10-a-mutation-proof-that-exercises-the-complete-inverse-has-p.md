> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **20 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A MUTATION PROOF THAT EXERCISES THE COMPLETE INVERSE HAS PROVED THE TIDY CASE

**Standing 2026-08-14. A refinement to the mutation-proof rule, not a
replacement — everything about proving a guard can go red still holds.**

The habit is to prove a guard by applying the COMPLETE inverse of the change:
delete the whole fix, watch the test redden, restore. That proves the guard sees
a total regression. **It does not prove the guard sees the regression that
actually ships.**

> **The failure that ships is a HALF-LANDED fix — the first edit the code's own
> comment invites, committed by somebody tired, with the other two layers still
> missing. Prove the guard against the PARTIAL fix, not only the total one.**

⚠️ **REFERENCE CASE, 2026-08-14 — a guard blind to the edit its own text asks
for.** An anti-stale arm existed to stop an exemption outliving its reason: it
watched a specialty sitting on a vocabulary exemption list and was meant to go
RED the moment a real bundle landed. Its author mutation-proved it and it fired
correctly — on the COMPLETE fix, where all three layers moved together (the
canonical key, the variant mapping, and the bundle).

It was silent on the **bundle-only** edit. And the bundle-only edit is precisely
what the exemption's own text invites the next person to do. The arm read
`SPECIALTY_KEYTERMS[normalizeSpecialty(id)]`, and the id had no variant mapping —
which was the very defect the exemption existed for — so it resolved to a
fallback key whose bundle is present-but-EMPTY. Land a real bundle and the arm
stays green forever: the guard written to stop an exemption outliving its reason
would have been the thing hiding it.

Three independent adversarial lenses found it; the author's own proof did not.

**Two things generalise, and the second is the cheaper one:**

1. **Enumerate the PARTIAL applications of your own fix and mutate to each.** If
   a fix touches three files, there are three one-file versions and three
   two-file versions, and a tired human lands one of them. The interesting
   mutations are usually not "delete everything" but "do the obvious first
   step".
2. **A present-but-empty fallback is the shape that makes a partial fix
   invisible.** `SPECIALTY_KEYTERMS.unspecified` exists and has zero terms, so
   the lookup succeeds, returns nothing, and no error is raised anywhere. Any
   time a lookup has a legal empty default, ask what a HALF-configured entry
   looks like to the guard — the answer is usually "identical to a correct one".

**Joint finding, two sessions, 2026-08-14** — one contributed the instance, the
other noticed it invalidates the way a whole series of mutation proofs had been
run that night (eight of them, every one exercising the complete inverse).

