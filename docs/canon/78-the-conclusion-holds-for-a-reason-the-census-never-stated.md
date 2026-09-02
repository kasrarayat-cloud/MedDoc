# "THE CONCLUSION HOLDS FOR A REASON THE CENSUS NEVER STATED" — THE CORRECTION FORM

**Recorded 2026-09-01, by owner ruling #163, which ratifies the FORM of the
correction and not merely the correction.**

## The case

A census was run before shipping a renderer change, to answer: *is any CERTIFIED
template's past blank proof suspect?* It measured, and it reconciled:

```
compiled versions 3 · field rows 150 = 98 content_control + 52 table_cell
legacy_form_field field rows          0
CERTIFIED versions                    1 (80 fields) — 0 legacy fields
```

Three independent routes agreed — the IR jsonb, a separate `rendererBinding`
column, and a raw `::text LIKE` scan of the whole blob. The conclusion drawn was:

> *"So no CERTIFIED template's past blank proofs are suspect."*

**The numbers are right. The sentence does not follow from them.**

`template_twin_compiled_versions.noteTemplateId` is UNIQUE and its children
cascade, so **a re-upload destroys the prior version's IR**. The audit log
disagreed with the census: two `TEMPLATE_TWIN_CERTIFIED` events, and the earlier
one's compiled version **no longer exists**.

    2026-07-26 | 471ba483…  still_exists = f  | fieldCount 80
    2026-08-20 | 617d6de9…  still_exists = t  | fieldCount 80

A census counts **survivors**. The question was about **the past**.

## The correction, and why its shape is the point

The honest repair was not to withdraw the conclusion — it happens to be true —
and not to defend the census. It was to say **which argument actually carries
it**:

> **The conclusion holds for a reason the census never stated:** the blank-proof
> machinery is itself unshipped. Measured with a positive control — `emptied`
> scores **0** occurrences in `main`'s two relevant files and **12** in the
> branch's — so no such proof has *ever* been emitted in production, by any
> template, certified or not.

That argument is immune to the cascade problem entirely. It does not care how
many versions were destroyed, because it says the artifact never existed.

## The form, stated for reuse

When a measurement is challenged and the conclusion survives:

1. **Say the measurement was insufficient**, in its own terms — *a census counts
   survivors; the claim was about the past*. Do not soften this into "the census
   was still broadly right".
2. **Name the argument that actually carries the conclusion**, and measure THAT,
   with its own positive control.
3. **Record what remains unmeasurable.** Here: the destroyed version's binding
   mix is gone and no instrument can recover it. That is a residual, stated, not
   a gap papered over by the surviving argument.
4. **Never let the original measurement keep the credit.** A true sentence
   sitting under the wrong evidence teaches the next reader to trust that kind
   of evidence for that kind of claim.

⚠️ **THE FAILURE THIS PREVENTS IS SPECIFIC AND COMFORTABLE:** the conclusion was
right, so every incentive pointed at leaving it alone. *A confirmed prediction
is not a control* — [canon 65](65-the-most-dangerous-wrong-number-is-the-one-expected.md)
— and a conclusion that survives its evidence being wrong is the same shape one
layer up. The census had reconciled three ways, which made it feel like the
strongest artifact in the report; reconciliation proves the number, never the
inference drawn from it.

**Related:** [canon 16](16-a-measurement-of-today-s-corpus-is-a-fact-about-the-popula.md)
— a measurement of today's corpus is a fact about the population, not a property
of the code. This is its temporal twin: a measurement of today's corpus is not a
fact about yesterday's either.
