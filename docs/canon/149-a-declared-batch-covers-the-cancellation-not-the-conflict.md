# A DECLARED BATCH COVERS THE CANCELLATION, NOT THE CONFLICT

**Standing 2026-09-09. Found by following the merge-side rule correctly and
having the second merge refused anyway.**

The merge-side rule offers two honest ways to merge a queue of PRs:

> *"After merging, WAIT for the merge commit's runs before merging the next PR.
> Or DECLARE THE BATCH IN ADVANCE — in the log, BEFORE the first merge."*

Both are about **whose evidence gets discarded**. Neither says anything about
whether the second PR still **applies**.

> **A declared batch buys you the right to cancel a run. It does not make two
> PRs that touch the same ledger mergeable back to back — the first merge
> invalidates the second's TREE, not its RUNS.**

## THE MEASUREMENT

Two PRs, both `MERGEABLE / CLEAN`, both carrying complete 4-of-4 citations,
`main` quiet, and the batch declared in the log before the first merge — every
requirement of the rule satisfied.

| step | result |
|---|---|
| merge #1018 | ✅ `a722b40f` |
| #1036, one second later | **`CONFLICTING / DIRTY`** |
| merge #1036 | 🔴 refused — `gh exit 1`, PR still `OPEN` |

Both branches carried rows in `docs/foundation/RULINGS.md` and
`docs/canon/INDEX.md`. The first merge put rows on `main` that the second
branch's tree did not have, and that is a **content conflict**, which no
declaration can address.

⚠️ **THE WRAPPER'S REFUSAL IS THE PART THAT WORKED.** It re-read the PR
afterwards rather than trusting the exit code, and said so plainly — *"NOT
merged. Not claiming a success that did not happen."* A wrapper that reported
the batch as complete would have left a ruled merge silently undone.

## AND CANON 147 ARRIVES WITHIN THE MINUTE

A `CONFLICTING` PR produces **no workflow runs at all**. So the second PR does
not merely fail to merge — it goes quiet, and every subsequent push to it cites
nothing while its checks tab shows the last green it ever earned. The batch
leaves the queue in the one state that looks fine and is not.

## THE HABIT

**A batch declaration is not a plan for merging PRs that share a file.** When
two queued PRs both touch the ledger, the canon index, or any accumulating
file:

1. merge the first,
2. **merge `main` into the second and resolve the union**, verifying by removal
   count and row membership,
3. let it earn a fresh citation,
4. then merge it.

That is not the batching rule failing — it is the batching rule answering a
different question. The cost is one extra citation cycle, and it is the honest
price of two changes to one ledger.

⚠️ **THE TELL, BEFORE YOU START:** if `git diff --name-only origin/main...HEAD`
on both PRs shares a file that only ever grows — `RULINGS.md`, `INDEX.md`,
`RELAY.md` — they are not batchable, whatever the run state says.
