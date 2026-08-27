# THE MOST DANGEROUS WRONG NUMBER IS THE ONE THE PREDICTION EXPECTS

**Ratified 2026-08-27.** The expected-wrongness family.

> **A wrong measurement that happens to equal what you predicted cannot be
> caught by reconciliation, because there is nothing left to disagree with.**

Every guard in this file assumes the same shape: a number arrives, you compare it
to what it should be, and a mismatch is the finding. *Arithmetic that does not
reconcile is a finding* works because wrongness is usually **incoherent** — a
partition that does not sum, a count that cannot be, a zero beside a one.

**This entry is the case where it is coherent.**

⚠️ **REFERENCE CASE, AND BOTH ACTORS HIT IT THE SAME DAY.** The F8 deploy had to
name how many migrations it would apply. `assert-migrations-applied.sh` was run
against the **shared tree**, which was several merges stale, and reported:

    🔴 UNAPPLIED MIGRATIONS — 1 in the repo never reached the database

**The truth on `main` was 2.** The second migration — F8-S2's refusal audit —
existed only on a commit the stale tree did not have.

**And `1` is exactly what the prediction said.** F8-S1's deploy hold had been
declared for two days as *"reads 🔴 1 unapplied on prod AND QA"*. So the wrong
number **matched the expectation perfectly**:

| | |
|---|---|
| what the instrument printed | `1 unapplied` |
| what the standing hold predicted | `1 unapplied` |
| what was true | **`2 unapplied`** |

A supervised session wrote `107 → 108` into a draft §2.5 declaration on that
basis, and the loop independently filed the same defect the same day, naming it
better than I did: *"the wrong number is the **expected** one, so nothing
incoherent exists to catch it."*

**WHAT ACTUALLY CAUGHT IT** was not arithmetic. It was re-running the check
against the **right tree** while computing the deploy range — i.e. asking the
question again of a different universe. The reconciliation had nothing to say,
because both sides of it were wrong in the same direction.

## THE PRACTICE

1. ⚠️ **A CONFIRMED PREDICTION IS NOT A CONTROL.** When a measurement agrees
   with a standing expectation, that agreement is the *weakest* possible
   evidence, not the strongest — it is exactly the case where a broken
   instrument is invisible. Treat "as expected" as a prompt to check the
   instrument, not as a reason to stop.
2. **ASK WHAT UNIVERSE THE INSTRUMENT IS ANSWERING ABOUT** before believing a
   number that matches. Here the instrument was perfect and the *tree* was
   stale — the watched-set failure, wearing a correct answer's clothes.
3. **A NUMBER THAT GATES AN IRREVERSIBLE ACT IS RE-DERIVED FROM THE ARTIFACT
   THE ACT WILL USE** — for a deploy, the deploy target, never the working
   copy. `git ls-tree -r origin/main` and the live database, not `ls` in
   whatever tree you are standing in.

**AND THE SIBLING SHAPE IS ALREADY IN THIS FILE**: *a documented defect is the
most convenient suspect.* There, a precedent explained the symptom and stopped
the search. Here, a prediction confirmed the symptom and stopped the search.
**Both are the search ending because something agreed with you.**
