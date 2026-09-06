# THE CHECK AND THE MERGE ARE NOT ATOMIC — A CORRECT TWO-VIEW CHECK STILL CANCELLED A CITATION

**Recorded 2026-09-05, from the composed deploy of `dcc8cabf`.**

> **`merge-pr.sh` reads `main`, decides, and then asks GITHUB to merge onto
> whatever `main`'s head is BY THEN.** A third party merging in that gap is
> invisible to the check by construction. No amount of care at the client
> closes it.

## The measurement

| at | what happened |
|---|---|
| — | two-view check on `main`: **0 in flight**, head `b13f3caa`. Correct at the time. |
| — | PR #971 merged, creating `43a2e511` and starting four fresh runs |
| — | `bash scripts/merge-pr.sh 970` merged **server-side onto `43a2e511`** → `b54a3b3a` |
| result | `43a2e511`'s **`e2e` and `CI` were CANCELLED** |

## Why the existing rule did not catch it

Every previously recorded occurrence is *"somebody pushed or merged without
checking"* or *"checked and deliberately proceeded"*. **This is neither.** The
check was performed, correctly, with both views, and returned a true answer
about the moment it was asked.

⚠️ **AND THE SAME GAP DEFEATED THE DECLARATION THREE TIMES IN ONE NIGHT.** The
declaration named `b13f3caa`; the merge produced `b54a3b3a` carrying **nine
runtime files it never named**, so `declaration_resolve` refused — correctly.
One structural gap, two different symptoms: a cancelled citation and an
unresolvable declaration.

## What recovers it, and what does not

**RECOVERED.** `b54a3b3a` is a DESCENDANT containing #971, so its own 4-of-4
citation certifies #971's code *plus* the merge that displaced it — strictly
stronger than the run that was lost. That is the documented descendant recovery
and it applies here with no special pleading.

**NOT RECOVERED.** The ~45 minutes #971's author would have waited, and the fact
that for a few minutes `main` carried a commit whose own citation had been
destroyed.

## The practice this DOES change

> **PIN THE DEPLOY TO A COMMIT, NOT TO `main`.**

Chasing `main` has no terminating condition: every re-statement costs a full CI
cycle, during which `main` can move again. Once a declaration's merge commit
exists and is cited, check the shared tree out to **that exact commit** and
deploy it. `main` may move afterwards; the deploy does not care. Production
lagging `main` between deploys is the normal state — the branch-cadence rule
forbids the opposite, production running code `main` does not have.

## What would actually close the gap

**Nothing on the client.** The deploy-candidate work reduces the BLAST RADIUS —
merges stop blocking on runs nobody is about to deploy — but does not make
check-and-merge atomic. The honest options are a merge queue, or accepting the
gap and relying on the descendant citation.

⚠️ **SO DO NOT WRITE A RULE TELLING THE NEXT SESSION TO CHECK HARDER.** It
checked correctly and the cancellation happened anyway. A rule that cannot be
obeyed into success is not a rule, it is a reprimand scheduled for somebody
else.
