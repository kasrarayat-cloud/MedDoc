# DECLARED BATCH — three loop PRs merged back-to-back, 2026-08-26

**Written and committed BEFORE the first merge, deliberately.** Canon is explicit
that *"declared at merge time is not a declaration, it is a narration"*, and the
mutation gate's lesson is that **"the file exists" is not "the file existed
first"** — only a commit timestamp proves precedence. This file's commit
timestamp is that proof; the merges follow it.

## WHAT IS BEING BATCHED, AND WHY

| PR | branch | what it carries |
|---|---|---|
| **#874** | `docs/ci-cost-arc-canon-resplit` | the CI cost arc into `docs/canon/`, and the index learns to count itself |
| **#875** | `feat/f29-orphan-branch-sweep` | the orphan-branch sweep; the ledger's own predicate was wrong by 64% |
| **#876** | `feat/f32-read-budget-guard` | the generalized read-budget guard — the guard this batch's successor depends on |

All three are the loop's own work, authored by sessions 01 and 02 of run
`20260826-140142-b1`. **The loop is HELD** at a STOP-file boundary under the
owner's ruling that the ledger split goes first, so no session is waiting on any
of these runs. There is no third-party evidence to destroy.

## THE COST BEING ACCEPTED, STATED PLAINLY

Merging back-to-back means each merge lands on `main` while the previous merge
commit's runs are in flight, and **GitHub cancels in-flight runs on a new commit
to the same branch.** So the intermediate merge-commit citations for #874 and
#875 will be cancelled. That is deliberate and it is this declaration's subject.

**Why the batch rather than three sequential waits:** there is exactly **one**
self-hosted runner (`quillmd-ci-1`) and it was carrying **12 queued runs** at
16:17Z. Sequential citation would be roughly `3 × (queue + ~50m e2e)` — measured
queues on this runner have run 57 to 88 minutes — i.e. the better part of a
working day, during which the loop stays dark and the ledger stays unreadable.

## WHAT DISCHARGES IT — the descendant citation, which is STRICTLY STRICTER

Canon's recovery pattern is not "re-run the cancelled past" — a cancelled run
describes an ancestor commit that is no longer `main`. It is:

> **cite the DESCENDANT — a full citation on the exact commit that will deploy.**

The final merge commit of this batch contains everything all three PRs
contained, so **one 4-of-4 citation on that head covers the same code plus the
rest of the batch**, and certifies the thing that actually ships rather than its
parent. That citation is owed and will be produced by
`bash scripts/check-citation.sh <FULL-40-CHAR-SHA>`, never typed.

## WHAT THIS DECLARATION DOES NOT COVER

- It does **not** authorize a deploy. Nothing here reaches production; §2.5 is
  untouched and the F8-S1 migration hold stands.
- It does **not** cover any PR beyond the three named above.
- It does **not** claim the cancelled runs were worthless — #874's `e2e` was
  `in_progress` when this was written, and that work is being discarded
  knowingly rather than unknowingly. That distinction is the entire point of
  declaring.
