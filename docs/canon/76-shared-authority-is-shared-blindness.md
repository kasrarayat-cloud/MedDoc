# SHARED AUTHORITY IS SHARED BLINDNESS — INDEPENDENT DISAGREEMENT WAS THE PROTECTION

**Recorded 2026-09-01, by owner ruling #163, which names it as a flaw in that
owner's own earlier ruling.**

Ruling #162(c) ordered that emptiness be proven by **byte-equality against the
writer's own expectation**. One span authority; no parsing, no allowlists. The
argument was sound and the implementation carried a comment saying so:

> *"ONE walk, two callers, so a widened renderer cannot outrun its own guard."*

**That sentence describes the defect.**

## What happened

The renderer's field walk was widened to fix a real harm — a two-paragraph
FORMTEXT whose stale `WARFARIN 5 MG DAILY` survived a null render. Widening it
made the verifier refuse the render, because the verifier's approved region was
still the begin's own paragraph. The obvious repair was to give both the SAME
walk.

With that done, a malformed field — an orphan `w:fldChar` `begin`, the ordinary
residue of deleting across a field boundary in Word — sent the window running
past its own field to the next `end` anywhere in the part. Measured, on a
document that compiles with zero unsupported nodes:

| token, present in SOURCE | `main` | after the shared walk |
|---|---|---|
| `ALLERGIES: PENICILLIN (ANAPHYLAXIS)` | present | **ERASED** |
| `ANTICOAGULATION HELD SINCE 2026-08-28` | present | **ERASED** |

`verified: true`. `fieldCheck: verified`. `staticRegionCheck: verified`. Proofs
`emptied`.

⚠️ **AND `main` REFUSED THAT SAME RENDER.** Its verifier, using its own
narrower notion of where the field ended, threw `STATIC_INVARIANCE_FAILED`. The
consolidation did not merely fail to catch the bug — **it removed a refusal that
already existed.**

## The generalisable half

> **A guard that derives its permission from the thing it guards cannot disagree
> with it.** Two implementations of the same question are a liability when they
> drift and a PROTECTION when they diverge, and you do not get to choose which
> one you are holding by writing a comment about it.

The de-duplication instinct is right almost everywhere, and this file is not an
argument against it. It is an argument about **which axis** is being shared:

- sharing a **parser**, a **formatter**, a **client** — good, and drift there is
  the classic defect;
- sharing the **predicate a check evaluates with the code it checks** — that is
  not de-duplication, it is **removing the second opinion**.

The tell is in the sentence you would write to justify it. *"One walk, two
callers, so the renderer cannot outrun its guard"* asserts a safety property
that the shared walk **cannot provide**, because the guard is now a function of
the walk. Ask instead: *if this walk is WRONG, what still says no?* If the
answer is "nothing", the sharing removed the control.

## The corollary about comments

The comment was written in good faith, was internally coherent, and was the
thing that made the change look finished. **A safety claim in a comment is a
hypothesis, and it is the one nobody tests** — the diff was proven by a suite,
mutation-proved on three arms, and typechecked, and none of those instruments
has any opinion about a sentence.

⚠️ **AND THE SAME PASS FOUND THE INSTRUMENT HAD NO COVERAGE AT ALL.** The
byte-equality comparison could be disabled outright — `if (false && …)` — and
**676 tests stayed green**, including the two arms named for it. So the
consolidation's blindness was not caught by the gate the consolidation was part
of, for the additional reason that the gate was inert.

**Related:** [canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)
(a control aimed where the answer is predetermined is not a control) — this is
its structural cousin: a control aimed at the thing that defines its own target.
And [canon 75](75-three-falsifications-is-data-about-the-instrument.md), which
is the arc this defect belongs to.
