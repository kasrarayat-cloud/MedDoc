# A GREEN STEP WHOSE SUCCESS IS COMPATIBLE WITH CANNOT-TELL MUST BE READ, NOT TRUSTED

**Standing 2026-09-07, from the ruling #210 proofs landing in CI.**

Some checks have **three** outcomes and only **two** exit codes to say them in.
When one of those outcomes is *"I could not tell"*, and it is mapped to success,
**the green stops meaning what its name says.**

## THE REFERENCE CASE

The race harness proving the last-owner trigger's advisory lock has three states
by design:

| exit | meaning |
|---|---|
| 0 | every predicted cell held |
| 1 | a prediction was **REFUTED** — a real finding |
| **2** | **CANNOT-TELL** — the two transactions never overlapped on this runner |

Exit 2 must not fail the build: *"the race did not happen here"* and *"the lock
is redundant"* are **different facts**, and treating them alike is how a flaky
red becomes a re-run and then a habit. So the CI step maps 2 to a `::warning`
and the step goes **green**.

> ⚠️ **WHICH MEANS A GREEN STEP THERE IS COMPATIBLE WITH THE PROOF NEVER HAVING
> RUN ITS CONTROL.**

On the first CI execution the step reported `success`. **That was not sufficient
to claim the harness passed**, and the log had to be read:

```
raceB : without lock 12/12 violations, with lock 0/12
🟢 RACE HARNESS PASSED — every predicted cell held.
```

It had passed — and the negative control fired **harder** on the runner than
locally (12/12 against 7–10/12). But that was a fact to be read, **not inferred
from the tick**.

## THE RULE

> **If a step's success is compatible with more than one outcome, its success is
> not a result. Read the output, or make the step narrower.**

Two ways to comply, and both are legitimate:

1. **Read it** — and say which outcome occurred, every time you cite it.
2. **Condition the success on the thing you actually mean.** The sibling arms
   step does this: `… && grep -q '🟢 all arms ran and passed'`, so it cannot go
   green merely because `psql` exited 0. **Where the assertion can be pushed
   into the step, push it.**

## ⚠️ AND THE THREE-STATE DESIGN IS NOT THE DEFECT — IT IS THE FIX

The temptation is to collapse exit 2 into a failure so the tick means one thing.
That trades an honest ambiguity for a dishonest certainty: a timing-dependent
proof that reds when the timing did not cooperate teaches everyone to re-run it,
and a check everyone re-runs is a check nobody reads.

**Keep the third state. Keep the warning. And never quote the tick as the
result.**
