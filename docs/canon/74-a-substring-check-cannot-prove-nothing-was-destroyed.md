# A SUBSTRING CHECK PROVES NOTHING WAS MANUFACTURED — IT CANNOT PROVE NOTHING WAS DESTROYED

**Ratified 2026-08-31, from ruling #157(b)'s adversarial pass.**

> **When a rule says "print the doctor's own words and compose nothing", the
> obvious property to assert is that the output is a SUBSTRING of the source.
> That property is necessary, cheap, and HALF OF THE ANSWER. Assert the other
> half in the same breath, or the guard reports green on the inversion of the
> thing it guards.**

## The specimen

Ruling #157(b) required that a denied narrative field print the doctor's
evidence quote **verbatim**, with zero composition and exactly one formatting
allowance — stripping a leading `<heading>:` token. The author (me) asserted
the composition property directly:

```ts
expect(quote.includes(printed) && quote.endsWith(printed)).toBe(true)
```

against text extracted from a really-rendered `word/document.xml`. It is a good
assertion. It cannot fail on manufactured text, and it did not.

⚠️ **AND IT WAS SATISFIED BY EVERY ONE OF THESE**, each measured end to end with
`valid: true`, zero validation issues, and the document rendered and verified:

| dictated, `polarity: denied` | printed into the signed document |
|---|---|
| `Negative for: diabetes, hypertension, and coronary artery disease.` | `diabetes, hypertension, and coronary artery disease.` |
| `Patient denies: chest pain and dyspnea.` | `chest pain and dyspnea.` |
| `Not taking: warfarin, aspirin, or clopidogrel.` | `warfarin, aspirin, or clopidogrel.` |
| `Without: fever, chills, or night sweats.` | `fever, chills, or night sweats.` |

The heading pattern's character class admitted **spaces**, and every token in the
repo's own `DENIAL_VOCABULARY` is letters-and-spaces — so ordinary structured
dictation puts the negation exactly where the pattern looks for a label, and the
strip **deleted the negation**. The third row prints an anticoagulant list for a
patient the encounter says is **not taking them**.

**Every output is a strict suffix of the doctor's own sentence.** Nothing was
manufactured. The meaning was inverted anyway.

## Why the shape recurs

A substring test asks *where did these bytes come from?* — a **provenance**
question. The rule it is standing in for asks *does this text still say what the
doctor said?* — a **meaning** question. Provenance is mechanically checkable and
meaning is not, so the checkable one gets asserted and quietly promoted to
standing for both. **The gap is invisible precisely because the assertion is
true.**

> **THE TELL: your assertion constrains only ONE DIRECTION of the edit.** Ask
> what the rule forbids. If it forbids *adding*, a subset check covers it. If it
> also forbids *removing* — and any rule about faithfulness does — a subset check
> is exactly half a guard, and the missing half is the one an attacker, a
> regex, or an ordinary sentence will find.

## The practice

**Name both properties and assert both.**

- **NOTHING MANUFACTURED** — the output is a substring of the source.
- **NOTHING DESTROYED** — a property that survives the edit and would fail if
  the meaning flipped. For #157(c) that is: the printed text must still contain
  an explicit negation token scoping the finding.

⚠️ **AND THE SECOND ASSERTION MUST NOT BE DRAWN FROM THE SAME LIST THE CODE
USES.** #157(b)'s repair guarded the strip with the exported `EXPLICIT_DENIAL`,
built from `DENIAL_VOCABULARY` — and the gate arm written to prove the repair
used **five fixtures that were all `DENIAL_VOCABULARY` tokens**. The arm's
result was fixed by its own target: mutating the guard out left every other
denial shape byte-identical, and the gate stayed **34 of 34 green**. That is the
*predetermined control* defect — see
[canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md) —
arriving one layer inside the fix for the defect it was written to catch.
**Fixtures for a vocabulary guard come from OUTSIDE the vocabulary.**

## The honest limit

The second property is a **heuristic about text**, and this programme has no
clinical NER. It can be wrong in both directions, and #157(c) accepts that
deliberately by choosing the safe one: a denial whose quote does not itself read
as a denial renders **BLANK with a named reason**, never a guess. **A blank is a
visible absence; an inverted sentence is a signed assertion.** When only one
direction can be cheap, buy the loud one.

---

## ⚠️ THE CAVEAT, ADDED 2026-08-31 BY #157(c) — GRANULARITY

**Both properties were asserted, and #157(c) satisfied both while printing a
false clinical assertion.**

    Chest pain / DENIED / "Denies chest pain at rest. Chest pain on exertion, 8 out of 10."
      -> rendered whole. Subset of the quote: TRUE. Contains a negation cue: TRUE.
      -> the signed field asserts 8/10 exertional chest pain under a DENIED fact.

The predicate scoped the cue to **one clause**; the printer printed **every
clause**. Both properties were true *of the whole text*, and the claim they stood
for was about *each clause*.

> **A PROPERTY CHECK MUST BE APPLIED AT THE GRANULARITY THE PROPERTY CLAIMS —
> WHOLE-TEXT CHECKS CANNOT PROVE PER-CLAUSE SCOPING.**

Two properties are better than one and neither count is the point: **ask what
UNIT your rule quantifies over, and assert at that unit.** This is the third
consecutive layer at which a green gate accompanied a live harm, which is
[canon 75](75-three-falsifications-is-data-about-the-instrument.md) — and it is
why #157(d) deletes the heuristic rather than adding a third property.
