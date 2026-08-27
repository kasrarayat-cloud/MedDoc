# A DOCUMENTED DEFECT IS THE MOST CONVENIENT SUSPECT

**Ratified 2026-08-27. The scapegoat pattern.**

> **When an instrument disagrees with you, CHECK YOUR OWN INPUT BEFORE YOU CHECK
> THE PRECEDENT.** A precedent has no way to tell you that you asked it the
> wrong question — it can only sit there being applicable.

This file is full of instruments that are documented to lie: `gh pr checks`
reporting `pending` for a finished run, `gh run list --commit` returning `[]` for
an abbreviated sha and again during the propagation window, `gh pr edit
--body-file` failing while printing a notice, `gh pr merge --delete-branch`
half-succeeding. **That library is an asset and it is also a hazard**, because
every one of those entries is a ready-made, well-evidenced, house-ratified
explanation for a symptom you are looking at right now.

⚠️ **REFERENCE CASE, 2026-08-27, AND THE SESSION HAD QUOTED THE RELEVANT ENTRY
THE SAME NIGHT.** Waiting on a citation, I ran `gh run list --commit <sha>` and
got `[]` while `--branch` showed four runs. There is an entry for exactly that —
the propagation-window divergence — and I recorded the observation in the session
log as *"a live sighting"* of it, **as corroboration**.

**It was not a sighting.** The sha was one I had written from MEMORY: correct
8-character prefix, thirty-two invented characters after it. `--commit` was
answering, correctly and instantly, about a commit that does not exist. Re-run
against the real sha it returned all four runs immediately.

**The instrument was flawless. The question was fiction. And the precedent fit
the symptom perfectly, which is the entire problem.**

⚠️ **NOTE WHAT THIS COST BEYOND THE HOUR.** It did not merely delay a diagnosis —
**it manufactured a false report and wrote it into the record as evidence for a
rule that did not apply.** The next session reading that log would have found
fresh corroboration for a defect that had not occurred. A wrong entry in this
file is worse than a missing one.

**THE MIRROR ENTRY, AND THEY ARE BOTH TRUE:** *"a documented-unreliable
instrument is not a permanently-wrong one"* warns that reaching for the
precedent instead of the data **discards true reports**. This is the same reflex
pointed the other way, and it **manufactures false ones**. In both cases the
error is identical: *the precedent was consulted in place of the measurement.*

## THE DENOMINATOR RULE, FILED BESIDE IT

The same night, the same fabricated sha exited a background wait loop that asked
*"how many runs on this sha are not completed?"* and got `0` — **because no run
matched the sha at all.** It printed `ALL RUNS COMPLETE` forty-eight seconds
after `e2e` had been observed `queued`. The next step was a merge on a citation
nobody had read; only the implausible arithmetic stopped it.

> **A COMPLETION CHECK NEEDS A DENOMINATOR, NEVER A BARE ZERO.**
>
>     [ "$TOTAL" -ge 4 ] && [ "$INCOMPLETE" = "0" ]     # not just INCOMPLETE == 0

*"Nothing is incomplete"* and *"nothing matched"* are two different facts that
collapse into the same number, which is this house's single most-repeated defect
— committed here inside a loop written to enforce rigour. **A non-vacuity floor
is one clause and it makes the two states distinguishable.**

**AND THE HABIT THAT PREVENTS THE WHOLE FAMILY:** an identifier reaches a command
from `rev-parse`, or from a JSON field, **in the same breath that uses it**.
Never from a variable set earlier, never from a display line, never from memory.

---

## ⚠️ TWO ACTORS, SAME DEFECT, SAME DAY — WHICH MAKES IT STRUCTURAL, NOT PERSONAL

**Appended 2026-08-27, hours after this entry was written.**

The FOUNDATION loop's session 02 close-out, filed independently and without
sight of this entry's drafting, reports:

> *"**I fabricated a 40-character SHA** and was one step from blaming the
> documented propagation window — second occurrence of a canon entry written
> *the same day*. I did it **three times** this session (a SHA, a run id, and an
> assertion count); the reflex is mine and recurring."*

So on one day: a supervised session invented a SHA and credited the empty result
to a documented instrument defect; and the loop did the same thing **three
times**, catching itself each time, and named the pattern as recurring.

⚠️ **THAT CHANGES WHAT THIS ENTRY IS.** A single instance reads as one actor
being careless on a long night — something a reader can file under *"I would
have checked."* **Four instances across two independent actors in one day is a
property of the WORK, not of the worker**: long sessions, dozens of 40-character
identifiers, a rich library of documented instrument defects that fit almost any
symptom, and no syntactic difference whatsoever between a real SHA and an
invented one.

**The consequence is that the cure must be MECHANICAL, not attentional.** "Be
careful with SHAs" has now failed four times in a day, twice by people who had
just written down the rule. What works is the habit stated at the top of this
entry — an identifier reaches a command from `rev-parse` or a JSON field **in
the same breath that uses it** — because that removes the opportunity rather
than asking for vigilance against it.
