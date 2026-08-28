# A PER-BRANCH INVARIANT IS NOT A MERGE INVARIANT

**Standing 2026-08-28. Caught one command before a batch merge, by looking at
what branches ADD rather than at whether each one is consistent.**

> **Nothing a single branch can assert about itself catches a collision that
> exists only in the UNION. Every branch can be internally perfect and compose
> into a broken `main`.**

## The case

Three branches were open, each adding canon entries:

| PR | adds |
|---|---|
| #890 | `69-a-byte-identity-row-needs-a-before-hash` · `70-an-exoneration-is-a-claim-too` |
| #894 | `69-a-refusal-caused-by-my-own-substitution` |
| #895 | `70-pin-properties-not-spellings` |

**Two canon 69s and two canon 70s.**

⚠️ **GIT WOULD NOT HAVE CAUGHT IT, AND THAT IS THE ENTIRE HAZARD.** The slugs
differ, so there is no filename conflict, no content conflict, and no failing
merge. All four files land cleanly. `main` then holds two entries numbered 69 and
two numbered 70, with the index pointing at whichever a reader happens to find
first. **Nothing fails. The numbering just quietly stops meaning anything.**

## What made it invisible

**Every branch reconciled INDIVIDUALLY.** All four worktrees were checked and
each one's stated entry count matched its own row count exactly:

    .f8-canon   stated=111 rows=111  OK
    .f5i2-queue stated=109 rows=109  OK
    .r23-fix    stated=108 rows=108  OK
    .r1-fence   stated=108 rows=108  OK

Four green checks, one broken union. The per-branch gate is not weak and it is
not misconfigured — **it is answering a question whose scope is smaller than the
failure.** A branch cannot see its siblings; asking it about them is asking the
wrong universe, which is the same family as
[a well-chosen fixture disguises a wrong universe](09-a-well-chosen-fixture-disguises-a-wrong-universe.md).

⚠️ **AND THE COUNT ARM ACTIVELY REASSURED.** Each branch's arithmetic added up,
so the one instrument watching this area reported green four times while the
collision was forming. *A reconciliation that reconciles within its own scope is
not evidence about a larger scope.*

## The cure — the gate lives where the union first exists

A duplicate-number arm cannot live on a branch. It lives on `main`, where the
merge result first exists, and it reds the **first post-merge run**:

- **canon** — no two bodies under `docs/canon/` share a numeric prefix, and no
  two index rows point at different files under one number
  (`gate-agents-md-size.test.ts`);
- **rulings** — every ruling number has exactly ONE base row, and a part letter
  is never reused within a number (`gate-ledger-reachability.test.ts`).

So a cross-branch collision that lands cleanly **dies within one citation instead
of living silently forever.** It cannot be prevented at merge time by any check a
branch can run; it can only be detected immediately after, and that is the
correct place for it.

⚠️ **THE RULINGS HALF IS NOT HYPOTHETICAL.** `RULINGS.md`'s own preamble records
that *"the loop and a supervised session collided on #124, then on #125"* — two
actors, one counter, no lock. The canon collision is the same shape in a
different namespace.

## ⚠️ THE INVARIANT WAS NARROWER THAN THE OBVIOUS ONE, AND THE OBVIOUS ONE WOULD HAVE SHIPPED BROKEN

A naive *"ruling numbers are unique"* arm **reds `main` on arrival**: five numbers
(#106, #109, #115, #116, #131) legitimately carry several rows, because an
amendment is a NEW ROW under the SAME number with a part marker in its title.

**Measure the existing population before writing the assertion.** A gate that has
to be disabled on its first run teaches everyone that gates are negotiable, which
costs more than the bug.

⚠️ **AND THE FIRST PROBE WAS WRONG IN THE SAME DIRECTION.** The part marker's
format varies in practice — `(g) —`, `b —`, `(c)-CORRECTED —` are all in use — so
a pattern matching only the parenthesised form reported #115 and #116 as
violations. **They were not violations; the probe was.** Two rounds of *the
instrument is the suspect* before the invariant was stated correctly.

The final form reconciles, which is what makes it believable:
**63 base + 7 part = 70 of 70 rows.**
