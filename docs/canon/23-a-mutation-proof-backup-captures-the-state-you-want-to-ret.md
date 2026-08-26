> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **41 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A MUTATION-PROOF BACKUP CAPTURES THE STATE YOU WANT TO **RETURN TO**

**Standing 2026-08-25.** Canon already says *restore from BACKUP, never from
git*. This is the refinement that rule was missing, and it cost the work twice
in one pass.

> **A PRE-CHANGE BACKUP TURNS "RESTORE" INTO "UNDO MY WORK".** The copy is taken
> to survive the mutation, so it must be of the state the mutation is applied
> TO — the finished change — not of whatever was there before you started.

⚠️ **REFERENCE CASE — a three-failure chain, each one masking the next.**

1. A change was written; a backup was taken **before** it, out of habit.
2. A mutation script referenced an env var the heredoc never exported. It threw
   — and **the suite ran anyway and printed `14 passed`.** An unapplied mutation
   yielding a green, exactly as canon predicts.
3. The "restore" copied the pre-change backup back — **destroying the change**
   and leaving a file that looked untouched because it *was* untouched.

**Only step 2's own assertion was working**; the green scrolled past beside it.
The loss was found by grepping for the new symbol and getting `0`.

**THE SHAPE THAT PREVENTS IT, and it is one line in a different order:**

    <write the change>
    cp <file> <scratch>/file.GOOD.bak      # <- AFTER the change, not before
    <mutate>; assert the marker is present  # <- before believing ANY result
    <run>; read the result
    cp <scratch>/file.GOOD.bak <file>       # <- returns to the CHANGE
    assert: marker gone AND the change's own symbol still present

⚠️ **THE LAST LINE IS THE ONE PEOPLE SKIP.** Asserting the mutation marker is
gone proves the mutation was undone. It says nothing about whether the thing you
were proving is still there. **Assert both: what must be absent, and what must
survive** — the same post-destruction discipline the reap rule already demands.


