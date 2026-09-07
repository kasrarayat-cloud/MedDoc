# A REPAIR CAN OPEN THE DEFECT STANDING NEXT TO IT — RE-DRIVE THE WHOLE CHAIN

**Standing 2026-09-07, from the #179 repair, and it is recorded because the
suite was green on both sides of the mistake.**

## THE REFERENCE CASE

Two defects sat next to each other on the L3 seam:

- **C2** — one off-lexicon ROS token failed a `.superRefine` over the whole
  array, discarding the entire extraction: chief complaint, medications, **and
  every allergy on the visit**.
- **C3** — the model was never shown the 72-token lexicon it was being judged
  against (measured: **1 of 72** tokens in the assembled prompt, and that one a
  false positive — the word *"frequency"* in the medications bullet).
- **C8** — 25 of the 72 tokens carry an underscore, and they reached the
  doctor's document as the fact's VALUE: `early_satiety`, `night_sweats`,
  `suicidal_ideation`, with `status=supported` and zero issues.

**C2's fix was to RESOLVE at the parse boundary instead of refusing** —
normalise, then coerce what remains to `other`, keeping the doctor's words in
`finding_verbatim`. That closed C8 *for the coerced case*: `"belching"` reached
the document as *"belching"*, not as `other`.

**C3's fix was to teach the model the lexicon**, generated from the shipped
constant, including the instruction *"use the identifier exactly as written —
lower case, underscores."*

⚠️ **AND THAT INSTRUCTION MADE C8 STRICTLY MORE LIKELY.** A COMPLIANT model now
emits `early_satiety`, so `finding === item.finding`, so **no verbatim is set at
all**, so the raw identifier flows to the document. Measured on the shipped
chain after both fixes:

    model says "early satiety"  ->  value "early satiety"    the doctor's words
    model says "early_satiety"  ->  value "early_satiety"    <- THE TOKEN, PRINTED

**Two correct fixes, landed together, and the second re-opened what the first
had closed — through a path neither fix's own arms looked at.**

## WHY NO TEST CAUGHT IT

Every arm was green throughout. C2's arms asserted the visit survives an
off-lexicon token; C3's asserted the prompt contains all 72 tokens. **Both were
true, and neither drove the chain from a MODEL RESPONSE to a DOCUMENT VALUE.**
Each arm measured its own seam and stopped there.

It surfaced only from re-running an end-to-end probe — `ExtractedEntities.parse`
→ `projectEncounterFacts` → the fact's `value` — that had been written for a
different question and was re-run out of habit.

## THE RULE

> **After landing a fix, RE-DRIVE THE WHOLE CHAIN — not the seam you changed.**
> A repair changes what the next stage receives, and the arms that pass are the
> ones written against what it used to receive.

⚠️ **AND WHEN TWO FIXES SHIP TOGETHER, ASK WHAT THE FIRST MAKES MORE COMMON.**
Here the first fix made `finding_verbatim` the carrier of the doctor's words,
and the second made the case where it is EMPTY the normal one. Neither author
of either half would have described that as a risk.

## THE COROLLARY IT EARNED

The fix — de-slug the token for display — **broke three existing arms, and they
were right to break.** `03-ros-polarity`'s helper located a fact by searching
its VALUE for the token (`String(f.value).includes('chest_pain')`), coupling
every arm in that file to the value being the raw machine identifier — the exact
thing a document must never print. Once the value read *"chest pain"* the lookup
found NOTHING and surfaced as `Cannot read properties of undefined`, not as a
wrong answer.

> **A HELPER THAT LOOKS SOMETHING UP BY ITS DISPLAY TEXT WILL BREAK CONFUSINGLY
> THE DAY THE DISPLAY IS FIXED.** Look up by the stable identifier — here the
> CONCEPT — and let the value be free to change.
