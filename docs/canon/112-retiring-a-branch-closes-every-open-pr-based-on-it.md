# RETIRING A BRANCH CLOSES EVERY OPEN PR THAT NAMES IT AS BASE — AND THAT CLOSE IS NOT REVERSIBLE

**Recorded 2026-09-05, from the T8 merge sequence.**

> **RETARGET BEFORE YOU RETIRE.** Before deleting any branch, repoint every open
> PR based on it onto the base it was going to land on anyway. Retargeting an
> **OPEN** pull request is one command and free. Retargeting a **CLOSED** one is
> refused — and deleting the branch is what closes it.

## The measurement

| at | what happened |
|---|---|
| `00:17:58Z` | **#946 merged** (head `feat/t8-icd10-fy2026-full`) |
| — | I retired that branch, deliberately, seconds later |
| `00:18:15Z` | **#951 CLOSED by GitHub** — head `feat/t8b-billable-descendants`, base `feat/t8-icd10-fy2026-full` |
| `02:38:36Z` | the work finally landed as **#967** — a NEW pull request, 2h20m later |

**Seventeen seconds, and no command of mine mentioned #951.**

⚠️ **THE MERGE DID NOT DO THIS — I DID.** `scripts/merge-pr.sh` does not pass
`--delete-branch`; it prints *"next: bash scripts/retire-branch.sh"*. So the
close was not a side effect of landing #946 that I could have been ambushed by.
It was a separate, deliberate act of tidying, taken while an open PR pointed at
the branch. **The tidy-up was the whole cause.**

## Both recovery doors are shut, and they shut in the wrong order

Attempted at the time, both refused:

    gh pr reopen 951   -> "Could not open the pull request"
    (retarget)         -> HTTP 422 "Cannot change the base branch of a closed
                                    pull request"

**Read those two together.** You may retarget an open PR, and you may not
retarget a closed one — so the operation that would have saved #951 is
available right up until the instant the deletion removes it. There is no state
in which you can notice the mistake and undo it: noticing happens after, and
after is exactly when the door is locked.

## What was lost, and what was not

The **code** was never at risk — it rebased onto `main` cleanly and became #967.
What did not survive was the **pull request object**: its number, its review
thread, its accumulated check history, and — the part that actually cost
something — **a ratification the board had already issued by number.** "#951 is
RATIFIED as built" now points at a closed PR that never merged. A citation was
silently invalidated by an act of housekeeping.

## ⚠️ AND THE GUARD THAT EXISTS CONFIRMS THE HARM

`scripts/retire-branch.sh` is a careful script. It exists *because*
`gh pr merge --delete-branch` is not atomic, and it refuses to claim a success
it did not earn — it checks both the local and the remote side and reports
honestly. Canon 64 records that its remote leg works.

**It did its job perfectly, and that is the point:**

> **A guard that confirms an act SUCCEEDED cannot tell you the act should not
> have been PERFORMED.** Every assertion it makes is about the deletion landing.
> None is about whether anything depended on the thing being deleted.

Measured today: `retire-branch.sh` contains **zero** references to `gh pr list`
or `baseRefName`. It has never been able to see a dependent PR, and nothing
about its clean green output hints at the gap.

## The practice

**One read, before the delete:**

    gh pr list --state open --base <branch> --json number,headRefName

**Non-empty means retarget first.** The door that works here is REST — measured
2026-09-05 on this `gh` build:

    gh api repos/<owner>/<repo>/pulls/<n> -X PATCH -f base=main   # exit 0

⚠️ **`gh pr edit --base` DOES NOT WORK IN THIS BUILD — it exits 1** on
`GraphQL: Projects (classic) is being deprecated … (repository.pullRequest.projectCards)`.
AGENTS.md already records that every `gh pr edit` in this build queries that
sunset field; this measurement confirms the failure reaches `--base`, not only
`--body-file`. **It prints as a deprecation notice and reads like a warning.
The retarget does not happen** — and a retarget you believe landed and did not
is the same lost PR by a longer road, so read the base back afterwards.

**The asymmetry is the whole argument for making this mechanical.** The check is
one read and costs nothing. The failure destroys an object that cannot be
reconstituted, in a system where nothing warns you and the tidy-up feels like
diligence.

⚠️ **THE MECHANISM IS ASSIGNED, NOT BUILT HERE.** An owner ruling of
2026-09-04 puts the dependent-PR guard inside `retire-branch.sh`, with the
session that owns the merge and retire tools.

⚠️ **AND IT IS DELIBERATELY NAMED BY DECISION RATHER THAN BY NUMBER.** That
ruling was issued as *#186*, and **no row claiming 186 exists on `main` or on
any branch** — the highest landed row is **#175**. `RULINGS.md`'s NUMBER-CLAIM
PROTOCOL is explicit that *a number is claimed by LANDING and only then*, and
that anything unlanded is referred to by its decision, never by a bare number,
because on a collision the merged row keeps the number and the unlanded one
renumbers. **A canon entry pointing at a number that later belongs to a
different decision is the wrong-pointer failure that protocol exists to
prevent** — so this entry points at the decision, and the number can be added
once its row lands. This entry is the standing habit for everyone else until it
lands — and it remains the habit afterwards, because a branch can also be
deleted from the GitHub UI, from `git push --delete`, and from a
`--delete-branch` flag that no local guard ever sees.
