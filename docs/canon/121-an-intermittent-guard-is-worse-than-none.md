# AN INTERMITTENT GUARD IS WORSE THAN NONE — ASSERT THE MECHANISM, NOT THE OUTCOME

**Standing 2026-09-07, from the ADMIN-5 last-owner work and the #206 reaper.**

A guard that refuses *most of the time* is not a weaker guard. It is a
**different and worse artifact than no guard at all**, because its existence is
what stops anyone from building the real one.

## THE TWO HALVES, AND THE SECOND IS THE ONE PEOPLE GET WRONG

**No guard** is a known gap. It appears in an audit as a gap, someone eventually
closes it, and in the meantime nobody relies on it.

**An intermittent guard** is a gap that has already been marked closed. It has a
name, a test, a line in a ledger and, usually, a green run behind it. Every
reader downstream — the next session, the reviewer, the person adding the sixth
door — treats the invariant as held, and each of them is right about the case
they checked.

> **The failure is not that it lets one write through. It is that it revokes
> everyone else's reason to look.**

## THE RULE

> **ASSERT THE MECHANISM, NOT THE OUTCOME.**

An outcome assertion asks *"did the bad thing happen this time?"* — and the
answer is `no` in every run where the race did not interleave, the pid happened
to still exist, the cache happened to be cold, or the door happened to be the
one that was guarded. **A green outcome is compatible with no mechanism at
all.**

A mechanism assertion asks *"is the thing that makes this impossible present,
and does removing it fail?"* That question has one answer and it does not depend
on timing.

## THE THREE INSTANCES THAT EARNED IT

**1 · A COUNT READ AND THEN ACTED ON.** ADMIN-5's failing interleaving, written
down before it was built: two owners demote each other at the same instant, the
count returns **2** to both, both conclude there is another owner, both write,
and the practice is left with **zero** owners. ⚠️ *That is not a window to
narrow — a read-then-act check cannot see it by construction*, so no amount of
testing the outcome distinguishes it from a correct guard. Ruled in SHAPE for
exactly this reason: a partial unique index or a SERIALIZABLE transaction,
**never** a count read and then acted on.

**2 · A GUARD PER DOOR.** Five surfaces reduce a practice's active-owner count —
role change, deactivation, suspension, soft-delete, self-service deletion — and
the set is open. A guard on the door you remembered is intermittent **in the
dimension of surfaces rather than of time**, and it reads as complete from
inside any one of them. Ruling #210's answer is the same move: enforce it once,
at the one place all the doors pass through, and let the mechanism be the thing
that is asserted.

**3 · A PID THAT WAS NEVER ALIVE.** The #206 reaper's aliveness check stamped
`$$` from a tool shell — a fresh subshell, dead before the marker was written
(canon 122). The refusal it implements is *"do not reap a live owner's tree"*,
and it would have refused correctly on any run where something else happened to
hold the tree. **Its outcome was defensible; its mechanism was absent.**

## THE TELL, AND THE TEST

**The tell:** you can describe a run in which the guard is satisfied *without
the guard doing anything* — a sequential execution of a "race" harness, a
happens-to-be-alive pid, a door that nobody exercised. If such a run exists and
the suite is green through it, the suite is measuring weather.

**The test is one question, and it is the same one canon 117 asks:** delete the
mechanism and run it. **If it stays green, the arm was never watching the
mechanism** — and where two enforcers stand in series, delete each one
separately, because a pair proves nothing about either member (ruling #212).

⚠️ **AND THE HONEST OPTION IS ALWAYS AVAILABLE.** If a guard genuinely cannot be
made total, say so and record it — `KNOWN_UNGUARDED` is that record. **A named
gap is worth more than a guard that closes it on average**, because the first
one is still visible to the person who has to fix it.
