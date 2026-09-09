# A REPO-WIDE SWEEP HAS NO PER-BRANCH TRUTH

**Standing 2026-09-08, after the class fired twice in two batches — once on a
rebase, once on a merge — and put `main` red the second time.**

> **A gate whose input is `git ls-files` is not measuring your branch. It is
> measuring a tree, and on a feature branch that tree is one that will never
> exist.** Its green there is not weak evidence. It is evidence about a
> different object.

## THE TWO INSTANCES

`gate-265-shellout-budgets` scans every tracked test file for a shell-out
timeout that exceeds its enclosing `it` budget — a real defect: the arm dies on
`Test timed out in 5000ms` and the subprocess's own message, the thing being
measured, is unreachable.

| when | what put the files in one tree | what it found |
|---|---|---|
| 2026-09-08, PR #1058 | a **REBASE** onto the newly-merged #1056 | **four** violations in `gate-container-revision.test.ts` |
| 2026-09-08, PR #1072 | the **MERGE** of #1064 beside it | **two** more in `gate-prove-mutation.test.ts` |
| 2026-09-08, PR #1073 | **THIS ENTRY'S OWN PR**, forked before #1072 landed | the same two, again |

The second is the argument. **#1066, #1067 and #1064 were each 4 of 4.** Every
per-PR citation was complete and honest. The sweep could not see #1064's new
file from #1058's branch, because on that branch the file did not exist.

## WHY IT IS NOT "RUN THE SUITE BEFORE MERGING"

That advice is already followed and does not help. The suite WAS run, on each
branch, and passed — correctly. The tree that fails is the one produced by the
merge, and it exists for the first time at the merge commit.

> **A PER-PR CITATION CANNOT SEE A CROSS-FILE SWEEP'S RESULT, BY CONSTRUCTION.**
> Not through carelessness, not through a stale base — the input to the gate is
> the union of two branches, and no branch holds the union.

⚠️ **AND THE SAME PROPERTY IS WHY THE GATE IS WORTH HAVING.** A per-file check
would never have found either set. The thing that makes it blind on a branch is
the thing that makes it valuable on `main`.

## WHAT ACTUALLY CATCHES IT

**The discharge citation on the FINAL merge commit, with the batch failing as a
UNIT.** That is not bookkeeping — it is the only place the union first exists.

The batch declaration written before the first merge said:

> *"the batch is not complete until that commit is 4 of 4, and it fails as a
> UNIT — no merge here is treated as discharged by its own cancelled run."*

It did exactly what it was written for. Had each PR been discharged on its own
4-of-4, all three would have read green and `main` would have gone to production
red.

## THE HABIT

1. **Never discharge a batch on its members' individual citations.** The
   descendant citation is the claim; the members' are inputs to it.
2. **When a gate's input is the repository rather than the diff, say so at the
   gate**, so the next author knows its branch result is provisional. A sweep
   that reads `git ls-files`, a size budget over a whole directory, an index
   that must reconcile with the files present — all the same shape.
3. ⚠️ **A CONTRACT A SWEEP OFFERS MUST BE DISCOVERABLE FROM THE FILE THAT NEEDS
   IT.** Both instances were fixed by one comment — `// shell-budget-governed-by:
   ARM_BUDGET_MS` — that the offending author had no way to know existed,
   because their branch was green. The gate's failure message should name the
   contract, not only the violation.
4. ⚠️ **AND A BRANCH FORKED BEFORE THE FIX CARRIES THE FAILURE — INCLUDING THE
   ONE DOCUMENTING IT.** This entry's own PR went red on exactly the two
   violations it describes, because it forked from `main` an hour before the fix
   merged. A repo-wide sweep is a property of a TREE, so every open branch
   inherits the defect until it rebases, and "my PR is docs-only" is not an
   exemption — the gate never looked at the diff. **Rebase before reading a red
   as new.**
5. **Expect the second instance.** #1058's own commit message describes the
   first in these words: *"THE REBASE PUT BOTH BRANCHES IN ONE TREE FOR THE
   FIRST TIME."* That sentence was written, merged, and then the identical thing
   happened via a merge four hours later. **Naming a class is not enumerating
   it** — canon already says so, and this is its next instance.

## THE COST, HONESTLY

One red `main` and one merge cycle. Nothing reached production: the deploy was
staged and held, because the declaration made the response mechanical rather
than a judgment call at 19:00.

**The cost it prevents** is the batch discharged on three green members, a red
`main` nobody looked at, and a deploy taken from it.
