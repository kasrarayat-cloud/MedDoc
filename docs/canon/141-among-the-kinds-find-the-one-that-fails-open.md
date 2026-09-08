# AMONG THE KINDS, FIND THE ONE THAT FAILS OPEN

**Ratified 2026-09-07, from ruling #247 Stage B's adversarial pass.**

`classifyFieldSource` decided that a control labelled `Patient` is filled from
the patient record. It read the LABEL, and only the label. Its own comment
reasoned carefully about two of the alternatives it was displacing — `manual`
and `verified_note_selection` — and never mentioned `checkbox`.

**A checkbox labelled `Patient` is ordinary on a consult form.** "History
provided by: ☐ Patient ☐ Family". "Consent given by: ☐ Patient ☐ Guardian".
Measured through the shipped chain, with the deterministic mapping builder and
no model anywhere in it:

```
mapping:    sourceType visit_metadata · concept visit_metadata.patient_name
            expectedDataType boolean
resolution: {"status":"record_derived","value":true,"reasonCode":"direct_evidence_supported"}
validation: valid, zero issues
counts:     {"filled":1,"recordDerived":1}
```

**The box is ticked because the chart has a name in it.** Nothing said yes to
whatever the box means, and the row's own caption tells the doctor the tick came
from the record.

⚠️ **THE MECHANISM IS THE GENERALISABLE PART.** The injector mints the fact with
`polarity: 'affirmed'` — stated, not inferred, which is canon 135 applied
correctly — and the resolver's checkbox arm reads **only** polarity and discards
the value entirely. That is right for a checkbox: a tick has no text. It is
catastrophic for a value that is *only* text.

> **A kind that ignores the value cannot fail closed on a wrong value.** Every
> other kind refuses a mis-typed fill on its own terms — a select refuses
> `select_value_not_exact_option`, a date refuses `date_not_unambiguous_iso`, a
> number refuses an unapproved unit — so a wrong value lands as an honest blank.
> The one that never looks at the value lands as a wrong ANSWER.

**THE METHOD, which is why this is canon and not a bug report.** The lens did not
guess; it swept **every** kind through the shipped chain and tabulated the
outcome. Seven of eight fail closed. One fills wrongly. *You cannot reason your
way to which one that is* — the arms differ per kind and the discarding one looks
like the simplest. **Enumerate the kinds and run each; the interesting one is
whichever discards the input your guard is protecting.**

**THE FIX HAS TWO WALLS, and the second is not belt-and-braces.** The classifier
now requires a kind that can carry the value (`narrative_text` or `number`), so
such a control is never classified that way. But **a certified mapping is DATA**
— restored, transferred between compiled versions, hand-editable — and the
classifier does not run again at fill time. So the injector checks the
`expectedDataType` it is actually filling. A guard that only runs at authoring
time does not guard anything that arrives another way.

**AND A CLASSIFIER GIVEN NO FIELD ANSWERS NO.** Several callers classify from a
label alone. A record-derived answer with no kind to check is a guess about a
control that prints a patient's identity, so the absent input resolves to the
ordinary answer rather than the special one.
