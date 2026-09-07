# AN ALARMING COUNT WITHOUT ITS SECOND QUERY IS NOT A FINDING

**Standing 2026-09-07, from ruling #222's ADMIN half.**

A number that sounds bad is not evidence that something is bad. It is evidence
that **you have asked one question**, and the second one is usually cheaper than
the first.

## THE REFERENCE CASE

> **"Six practices have zero active owners."**

True, measured, and alarming — it is exactly the state the last-owner invariant
exists to prevent, sitting in production six times over.

**The second query:**

```
practices with a LIVE member and NO able owner (the real harm) ....... 0
```

**Nobody is stranded.** All six are inert: every member of every one is
inactive, all seven users carry test-shaped emails, none holds a single visit.
Five are `Solo — QA …` signup shells minted on one day by a QA run exercising
signup edge cases; the sixth is an April test clinic.

**The first number is a count of a SHAPE. The second is a count of the HARM.**
They differ by every case where the shape exists and the harm does not, and that
was all of them.

## WHY THIS IS A TRAP AND NOT JUST AN OVERSIGHT

⚠️ **THE ALARMING COUNT IS SELF-JUSTIFYING.** It arrives already looking like a
finding, so it does not prompt the question that would deflate it. Nobody asks
*"and how many of those matter?"* about a number that has already been accepted
as bad — the acceptance is what stops the asking.

⚠️ **AND IT DRIVES THE WRONG WORK.** Six stranded practices is an incident. Six
abandoned test shells is a chore. The two get different urgency, different
scope, and different people — and the count alone cannot tell you which you
have.

## THE RULE

> **Before reporting a count as a finding, ask what it would take for each
> member of that count to be HARMLESS — then measure how many are.**

The gap between the two numbers is the finding. Sometimes it is zero and the
alarm was right; here it was the whole population.

**Corollary:** report both. A report that gives only the harm count hides the
shape, and the shape is what a guard has to handle — the six inert practices are
precisely why the last-owner trigger needs its "already at zero stays writable"
exemption, and a report that had mentioned only *"nobody is stranded"* would
have made that exemption look unnecessary.

## THE SIBLING

This is the population-first habit pointed at a number rather than at a query:
*"query the POPULATION before diagnosing one user"*. Same instinct, other end —
there, one case was generalised without checking how many; here, a count was
accepted without checking what it contained.
